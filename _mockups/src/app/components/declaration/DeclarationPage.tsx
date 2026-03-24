import { useState, useRef, useCallback } from "react";
import { DeclHeader } from "./DeclHeader";
import { SummaryStrip } from "./SummaryStrip";
import { PrintedForm } from "./PrintedForm";
import { SourceDrawer } from "./SourceDrawer";
import { DocsSidebar } from "./DocsSidebar";
import { BottomBar } from "./BottomBar";
import { getFieldInfo } from "./fieldData";
import { AnimatePresence, motion } from "motion/react";
import { Resizable } from "re-resizable";

export function DeclarationPage() {
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [drawerWidth, setDrawerWidth] = useState(480);
  const [docsOpen, setDocsOpen] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [cellOverrides, setCellOverrides] = useState<Record<string, string>>({});
  const [forceSourceTab, setForceSourceTab] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const fieldInfo = selectedField ? getFieldInfo(selectedField) : null;
  const isOpen = fieldInfo != null;

  const handleFieldSelect = (id: string) => {
    setSelectedField(prev => prev === id ? null : id);
    setForceSourceTab(false);
    if (editingField && editingField !== id) {
      setEditingField(null);
    }
  };

  const handleStartManualEdit = useCallback((id?: string) => {
    const targetId = id ?? selectedField;
    if (targetId) {
      setSelectedField(targetId);
      setEditingField(targetId);
      setForceSourceTab(false);
    }
  }, [selectedField]);

  const handleSaveEdit = useCallback((id: string, newValue: string) => {
    setCellOverrides(prev => ({ ...prev, [id]: newValue }));
    setEditingField(null);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingField(null);
  }, []);

  const handleApplySourceValue = useCallback((value: string) => {
    if (selectedField) {
      setCellOverrides(prev => ({ ...prev, [selectedField]: value }));
    }
  }, [selectedField]);

  const handleOpenSourceChange = useCallback((id: string) => {
    setSelectedField(id);
    setEditingField(null);
    setForceSourceTab(true);
  }, []);

  return (
    <div className="h-screen w-full flex flex-col bg-[#f8f8fa] overflow-hidden" style={{ minWidth: 1280 }}>
      <DeclHeader docsOpen={docsOpen} onToggleDocs={() => setDocsOpen(v => !v)} />
      <SummaryStrip />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left docs sidebar */}
        <AnimatePresence>
          {docsOpen && (
            <motion.div
              key="docs-sidebar"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 300, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 400, damping: 34 }}
              className="shrink-0 overflow-hidden"
            >
              <div className="h-full w-[300px]">
                <DocsSidebar onClose={() => setDocsOpen(false)} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <PrintedForm
          selectedField={selectedField ?? ""}
          onFieldSelect={handleFieldSelect}
          contentRef={contentRef}
          editingField={editingField}
          cellOverrides={cellOverrides}
          onSaveEdit={handleSaveEdit}
          onCancelEdit={handleCancelEdit}
          onStartManualEdit={(id) => handleStartManualEdit(id)}
          onOpenSourceChange={handleOpenSourceChange}
        />
        <AnimatePresence>
          {isOpen && (
            <motion.div
              key="source-drawer"
              initial={{ width: 0 }}
              animate={{ width: drawerWidth }}
              exit={{ width: 0 }}
              transition={{ type: "spring", stiffness: 400, damping: 34 }}
              className="shrink-0 overflow-hidden"
            >
              <Resizable
                size={{ width: drawerWidth, height: "100%" }}
                onResizeStop={(_e, _dir, _ref, d) => setDrawerWidth(w => w + d.width)}
                minWidth={360}
                maxWidth={720}
                enable={{ left: true, right: false, top: false, bottom: false, topRight: false, bottomRight: false, bottomLeft: false, topLeft: false }}
                handleStyles={{ left: { width: 4, left: 0, cursor: "col-resize" } }}
                handleClasses={{ left: "hover:bg-slate-300/50 active:bg-slate-400/50 transition-colors" }}
              >
                <div className="h-full">
                  <SourceDrawer
                    field={fieldInfo!}
                    onClose={() => { setSelectedField(null); setForceSourceTab(false); }}
                    onStartManualEdit={() => handleStartManualEdit()}
                    onApplySourceValue={handleApplySourceValue}
                    isEditing={editingField === selectedField}
                    forceSourceTab={forceSourceTab}
                  />
                </div>
              </Resizable>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <BottomBar />
    </div>
  );
}