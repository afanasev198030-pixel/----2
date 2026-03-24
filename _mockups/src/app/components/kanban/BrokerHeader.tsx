import { Plus, Search, Bell, User, LayoutGrid, Command } from "lucide-react";

export function BrokerHeader() {
  return (
    <header className="sticky top-0 z-50 bg-white border-b border-slate-200/70" style={{ minHeight: 56 }}>
      <div className="flex items-center justify-between px-6 h-14">
        {/* Left: Logo + title */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-sm">
            <LayoutGrid className="w-4 h-4 text-white" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-[15px] text-slate-900 tracking-[-0.01em]" style={{ fontWeight: 600 }}>Customs AI</span>
            <div className="h-4 w-px bg-slate-200" />
            <span className="text-[12px] text-slate-400 tracking-[-0.01em]" style={{ fontWeight: 400 }}>Панель брокера</span>
          </div>
        </div>

        {/* Center: Search */}
        <div className="flex items-center bg-slate-50/80 border border-slate-200/60 rounded-[10px] px-3 py-2 w-[360px] hover:border-slate-300/80 transition-colors focus-within:border-slate-300 focus-within:bg-white focus-within:shadow-sm">
          <Search className="w-3.5 h-3.5 text-slate-400 mr-2 shrink-0" />
          <input
            type="text"
            placeholder="Поиск по ID, клиенту, ТН ВЭД..."
            className="bg-transparent text-[12px] text-slate-700 placeholder:text-slate-400 outline-none w-full"
          />
          <kbd className="hidden sm:flex items-center gap-0.5 ml-2 px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200/80 text-[10px] text-slate-400 shrink-0">
            <Command className="w-2.5 h-2.5" />K
          </kbd>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2.5">
          <button className="flex items-center gap-2 px-4 py-2 rounded-[10px] bg-slate-900 text-white text-[12px] hover:bg-slate-800 transition-all shadow-sm hover:shadow-md active:scale-[0.98]" style={{ fontWeight: 500 }}>
            <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
            Создать декларацию
          </button>
          <div className="w-px h-6 bg-slate-150 mx-0.5" />
          <button className="relative p-2 rounded-[10px] hover:bg-slate-50 text-slate-400 hover:text-slate-600 transition-colors">
            <Bell className="w-[18px] h-[18px]" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-white" />
          </button>
          <button className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center text-slate-500 hover:from-slate-200 hover:to-slate-300 transition-all ring-1 ring-slate-200/50">
            <User className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
