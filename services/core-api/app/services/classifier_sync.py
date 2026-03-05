"""
Classifier synchronization service.

Handles full and incremental sync of EEC classifiers
from portal.eaeunion.org into the local PostgreSQL database.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_sessionmaker
from app.models import Classifier, ClassifierSyncLog
from .eec_classifier_config import EEC_CLASSIFIERS
from .eec_connector import EecODataConnector

logger = structlog.get_logger()

SENTINEL_END_DATE_YEAR = 8900


@dataclass
class SyncResult:
    classifier_type: str
    status: str = "success"
    records_total: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_deactivated: int = 0
    error: Optional[str] = None


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime from OData response, treating 8900-year values as None (indefinite).

    Returns timezone-naive datetimes (DB column is TIMESTAMP WITHOUT TIME ZONE).
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.year >= SENTINEL_END_DATE_YEAR:
            return None
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _map_item(item: dict, config: dict, classifier_type: str) -> dict:
    """Transform a single OData item into a dict suitable for Classifier upsert."""
    code = str(item.get(config["code_field"]) or "").strip()
    name = str(item.get(config["name_field"]) or "").strip()

    end_dt = _parse_datetime(item.get("EndDate"))
    start_dt = _parse_datetime(item.get("StartDate"))

    is_active = True
    if end_dt is not None:
        is_active = end_dt > datetime.utcnow()

    meta: dict = {}
    for local_key, remote_key in config.get("extra_fields", {}).items():
        val = item.get(remote_key)
        if val is not None:
            meta[local_key] = str(val).strip()

    return {
        "classifier_type": classifier_type,
        "code": code,
        "name_ru": name,
        "source": "eec_portal",
        "eec_record_id": item.get("ID"),
        "start_date": start_dt,
        "end_date": end_dt,
        "is_active": is_active,
        "meta": meta if meta else None,
    }


async def full_sync(
    classifier_type: str,
    connector: Optional[EecODataConnector] = None,
) -> SyncResult:
    """Download all records for a classifier and upsert into the database."""
    config = EEC_CLASSIFIERS.get(classifier_type)
    if not config:
        return SyncResult(classifier_type=classifier_type, status="error", error="Unknown classifier type")

    result = SyncResult(classifier_type=classifier_type)
    conn = connector or EecODataConnector()

    try:
        items = await conn.get_items(config["guid"])
        result.records_total = len(items)

        async with async_sessionmaker() as session:
            existing_codes: set[str] = set()
            rows = await session.execute(
                select(Classifier.code, Classifier.eec_record_id).where(
                    Classifier.classifier_type == classifier_type,
                )
            )
            for row in rows.all():
                existing_codes.add(row[0])

            portal_codes: set[str] = set()

            for item in items:
                mapped = _map_item(item, config, classifier_type)
                if not mapped["code"]:
                    continue

                portal_codes.add(mapped["code"])

                existing = await session.execute(
                    select(Classifier).where(
                        Classifier.classifier_type == classifier_type,
                        Classifier.code == mapped["code"],
                    )
                )
                record = existing.scalar_one_or_none()

                if record:
                    record.name_ru = mapped["name_ru"]
                    record.source = "eec_portal"
                    record.eec_record_id = mapped["eec_record_id"]
                    record.start_date = mapped["start_date"]
                    record.end_date = mapped["end_date"]
                    record.is_active = mapped["is_active"]
                    if mapped["meta"]:
                        record.meta = {**(record.meta or {}), **mapped["meta"]}
                    result.records_updated += 1
                else:
                    new_record = Classifier(
                        classifier_type=mapped["classifier_type"],
                        code=mapped["code"],
                        name_ru=mapped["name_ru"],
                        source=mapped["source"],
                        eec_record_id=mapped["eec_record_id"],
                        start_date=mapped["start_date"],
                        end_date=mapped["end_date"],
                        is_active=mapped["is_active"],
                        meta=mapped["meta"],
                    )
                    session.add(new_record)
                    result.records_created += 1

            stale_codes = existing_codes - portal_codes
            if stale_codes:
                stale = await session.execute(
                    select(Classifier).where(
                        Classifier.classifier_type == classifier_type,
                        Classifier.code.in_(stale_codes),
                        Classifier.source == "eec_portal",
                    )
                )
                for record in stale.scalars().all():
                    record.is_active = False
                    result.records_deactivated += 1

            await _update_sync_log(
                session, classifier_type, config["guid"], result,
            )
            await session.commit()

        logger.info(
            "classifier_full_sync_done",
            type=classifier_type,
            total=result.records_total,
            created=result.records_created,
            updated=result.records_updated,
            deactivated=result.records_deactivated,
        )

    except Exception as exc:
        result.status = "error"
        result.error = str(exc)
        logger.error("classifier_full_sync_failed", type=classifier_type, error=str(exc))
        try:
            async with async_sessionmaker() as session:
                await _update_sync_log(
                    session, classifier_type, config["guid"], result,
                )
                await session.commit()
        except Exception:
            pass

    return result


async def incremental_sync(
    classifier_type: str,
    connector: Optional[EecODataConnector] = None,
) -> SyncResult:
    """Download only records modified since last sync."""
    config = EEC_CLASSIFIERS.get(classifier_type)
    if not config:
        return SyncResult(classifier_type=classifier_type, status="error", error="Unknown classifier type")

    async with async_sessionmaker() as session:
        log = await session.execute(
            select(ClassifierSyncLog).where(
                ClassifierSyncLog.classifier_type == classifier_type,
                ClassifierSyncLog.status == "success",
            ).order_by(ClassifierSyncLog.last_sync_at.desc()).limit(1)
        )
        last_log = log.scalar_one_or_none()

    if not last_log or not last_log.last_modification_check:
        logger.info("no_previous_sync, falling back to full", type=classifier_type)
        return await full_sync(classifier_type, connector)

    result = SyncResult(classifier_type=classifier_type)
    conn = connector or EecODataConnector()

    try:
        items = await conn.get_items_modified_since(
            config["guid"], last_log.last_modification_check,
        )
        result.records_total = len(items)

        if not items:
            logger.info("incremental_sync_no_changes", type=classifier_type)
            async with async_sessionmaker() as session:
                await _update_sync_log(
                    session, classifier_type, config["guid"], result,
                )
                await session.commit()
            return result

        async with async_sessionmaker() as session:
            for item in items:
                mapped = _map_item(item, config, classifier_type)
                if not mapped["code"]:
                    continue

                existing = await session.execute(
                    select(Classifier).where(
                        Classifier.classifier_type == classifier_type,
                        Classifier.code == mapped["code"],
                    )
                )
                record = existing.scalar_one_or_none()

                if record:
                    record.name_ru = mapped["name_ru"]
                    record.source = "eec_portal"
                    record.eec_record_id = mapped["eec_record_id"]
                    record.start_date = mapped["start_date"]
                    record.end_date = mapped["end_date"]
                    record.is_active = mapped["is_active"]
                    if mapped["meta"]:
                        record.meta = {**(record.meta or {}), **mapped["meta"]}
                    result.records_updated += 1
                else:
                    new_record = Classifier(
                        classifier_type=mapped["classifier_type"],
                        code=mapped["code"],
                        name_ru=mapped["name_ru"],
                        source=mapped["source"],
                        eec_record_id=mapped["eec_record_id"],
                        start_date=mapped["start_date"],
                        end_date=mapped["end_date"],
                        is_active=mapped["is_active"],
                        meta=mapped["meta"],
                    )
                    session.add(new_record)
                    result.records_created += 1

            await _update_sync_log(
                session, classifier_type, config["guid"], result,
            )
            await session.commit()

        logger.info(
            "classifier_incremental_sync_done",
            type=classifier_type,
            total=result.records_total,
            created=result.records_created,
            updated=result.records_updated,
        )

    except Exception as exc:
        result.status = "error"
        result.error = str(exc)
        logger.error("classifier_incremental_sync_failed", type=classifier_type, error=str(exc))

    return result


async def sync_all(force_full: bool = False) -> dict[str, SyncResult]:
    """Synchronize all 29 classifiers. Uses incremental sync when possible."""
    from app.config import settings
    results: dict[str, SyncResult] = {}
    connector = EecODataConnector(base_url=settings.EEC_PORTAL_BASE_URL)

    for classifier_type in EEC_CLASSIFIERS:
        if force_full:
            res = await full_sync(classifier_type, connector)
        else:
            res = await incremental_sync(classifier_type, connector)
        results[classifier_type] = res
        await asyncio.sleep(0.5)

    success = sum(1 for r in results.values() if r.status == "success")
    failed = sum(1 for r in results.values() if r.status == "error")
    logger.info("sync_all_completed", success=success, failed=failed)

    return results


async def _update_sync_log(
    session: AsyncSession,
    classifier_type: str,
    eec_guid: str,
    result: SyncResult,
) -> None:
    """Create or update the sync log entry for a classifier type."""
    log = ClassifierSyncLog(
        classifier_type=classifier_type,
        eec_guid=eec_guid,
        last_sync_at=datetime.utcnow(),
        last_modification_check=date.today() if result.status == "success" else None,
        records_total=result.records_total,
        records_updated=result.records_created + result.records_updated,
        status=result.status,
        error_message=result.error,
    )
    session.add(log)
