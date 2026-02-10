"""
Seed data loader for customs declaration system.

Loads classifiers (countries, currencies, transport types, etc.) and creates
default admin user and company.

Usage:
    python -m app.seeds.load
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_sessionmaker
from app.models import Classifier, User, Company, HsRequirement
from app.middleware.auth import get_password_hash
from app.models.user import UserRole


# Mapping of JSON files to classifier types
SEED_FILES = {
    "countries.json": "country",
    "currencies.json": "currency",
    "transport_types.json": "transport_type",
    "incoterms.json": "incoterms",
    "deal_nature.json": "deal_nature",
    "mos_methods.json": "mos_method",
    "procedures.json": "procedure",
}


async def load_classifiers(session: AsyncSession) -> dict[str, int]:
    """Load all classifier seed files into the database."""
    seeds_dir = Path(__file__).parent
    summary = {}
    
    for filename, classifier_type in SEED_FILES.items():
        filepath = seeds_dir / filename
        
        if not filepath.exists():
            print(f"Warning: {filename} not found, skipping...")
            continue
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        loaded_count = 0
        skipped_count = 0
        
        for item in data:
            code = item.get("code")
            name_ru = item.get("name_ru")
            name_en = item.get("name_en")
            
            if not code:
                print(f"Warning: Skipping item in {filename} - missing 'code'")
                continue
            
            # Check if classifier already exists
            result = await session.execute(
                select(Classifier).where(
                    Classifier.classifier_type == classifier_type,
                    Classifier.code == code
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                skipped_count += 1
                continue
            
            # Create new classifier
            classifier = Classifier(
                classifier_type=classifier_type,
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                is_active=True
            )
            session.add(classifier)
            loaded_count += 1
        
        await session.commit()
        summary[classifier_type] = {"loaded": loaded_count, "skipped": skipped_count}
        print(f"✓ {classifier_type}: loaded {loaded_count}, skipped {skipped_count}")
    
    return summary


async def load_hs_requirements(session: AsyncSession) -> dict[str, int]:
    """Load HS code requirements (certificates, licenses, permits) from seed file."""
    seeds_dir = Path(__file__).parent
    filepath = seeds_dir / "hs_requirements.json"

    if not filepath.exists():
        print("Warning: hs_requirements.json not found, skipping...")
        return {"loaded": 0, "skipped": 0}

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    loaded_count = 0
    skipped_count = 0

    for item in data:
        hs_code_prefix = item.get("hs_code_prefix")
        requirement_type = item.get("requirement_type")
        document_name = item.get("document_name")

        if not hs_code_prefix or not document_name:
            print(f"Warning: Skipping HS requirement - missing required fields")
            continue

        # Check if this exact requirement already exists
        result = await session.execute(
            select(HsRequirement).where(
                HsRequirement.hs_code_prefix == hs_code_prefix,
                HsRequirement.requirement_type == requirement_type,
                HsRequirement.document_name == document_name,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            skipped_count += 1
            continue

        requirement = HsRequirement(
            hs_code_prefix=hs_code_prefix,
            requirement_type=requirement_type,
            document_name=document_name,
            issuing_authority=item.get("issuing_authority"),
            legal_basis=item.get("legal_basis"),
            description=item.get("description"),
            is_active=True,
        )
        session.add(requirement)
        loaded_count += 1

    await session.commit()
    print(f"✓ hs_requirements: loaded {loaded_count}, skipped {skipped_count}")
    return {"loaded": loaded_count, "skipped": skipped_count}


async def create_default_admin(session: AsyncSession, company_id=None) -> tuple[bool, str]:
    """Create default admin user if it doesn't exist."""
    result = await session.execute(
        select(User).where(User.email == "admin@customs.local")
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        return False, "Admin user already exists"
    
    # Create admin user
    admin_user = User(
        email="admin@customs.local",
        hashed_password=get_password_hash("admin123"),
        full_name="Администратор",
        role=UserRole.ADMIN.value,
        is_active=True,
        company_id=company_id,
    )
    session.add(admin_user)
    await session.flush()
    
    return True, f"Created admin user: {admin_user.email} (company_id: {company_id})"


async def create_default_company(session: AsyncSession) -> tuple[bool, str]:
    """Create default company if it doesn't exist."""
    result = await session.execute(
        select(Company).where(Company.inn == "1234567890")
    )
    existing_company = result.scalar_one_or_none()
    
    if existing_company:
        return False, "Default company already exists"
    
    # Create default company
    company = Company(
        name="ООО Тест",
        inn="1234567890",
        country_code="RU"
    )
    session.add(company)
    await session.flush()  # Flush to get the company ID
    
    return True, f"Created company: {company.name} (INN: {company.inn})"


async def main():
    """Main function to load all seed data."""
    print("=" * 60)
    print("Loading seed data for customs declaration system")
    print("=" * 60)
    
    async with async_sessionmaker() as session:
        try:
            # Load classifiers
            print("\nLoading classifiers...")
            summary = await load_classifiers(session)

            # Load HS requirements
            print("\nLoading HS code requirements...")
            hs_req_summary = await load_hs_requirements(session)
            summary["hs_requirements"] = hs_req_summary

            # Create default company first
            print("\nCreating default company...")
            company_created, company_msg = await create_default_company(session)
            if company_created:
                await session.commit()
            print(f"  {company_msg}")
            
            # Get company for admin association
            result = await session.execute(
                select(Company).where(Company.inn == "1234567890")
            )
            company = result.scalar_one_or_none()
            
            # Create default admin user linked to company
            print("\nCreating default admin user...")
            admin_created, admin_msg = await create_default_admin(session, company_id=company.id if company else None)
            if admin_created:
                await session.commit()
            print(f"  {admin_msg}")
            
            # Print summary
            print("\n" + "=" * 60)
            print("Summary:")
            print("=" * 60)
            total_loaded = sum(s["loaded"] for s in summary.values())
            total_skipped = sum(s["skipped"] for s in summary.values())
            print(f"Classifiers loaded: {total_loaded}")
            print(f"Classifiers skipped (already exist): {total_skipped}")
            print("\nBreakdown by type:")
            for classifier_type, counts in summary.items():
                print(f"  {classifier_type}: {counts['loaded']} loaded, {counts['skipped']} skipped")
            
            print("\n✓ Seed data loading completed successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n✗ Error loading seed data: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
