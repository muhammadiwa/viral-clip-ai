import React from "react";
import { motion } from "framer-motion";

const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 border-r border-slate-200 bg-white/80 backdrop-blur sticky top-0 h-screen">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold">
          VC
        </div>
        <div>
          <div className="font-semibold text-sm">Muhammad Iwa</div>
          <div className="text-xs text-slate-500">3 Channels • 0 credits</div>
        </div>
      </div>

      <nav className="px-4 py-4 text-sm space-y-6">
        <div>
          <div className="mb-1 text-xs font-semibold text-slate-400">CREATE</div>
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-100">
            Home
          </button>
        </div>

        <div>
          <div className="mb-1 text-xs font-semibold text-slate-400">AI Tools</div>
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-100">
            AI Script
          </button>
          <motion.button
            className="w-full text-left mt-1 px-3 py-2 rounded-lg bg-primary text-white shadow-sm"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            AI Viral Clip
          </motion.button>
          <button className="w-full text-left mt-1 px-3 py-2 rounded-lg hover:bg-slate-100">
            Caption Generator
          </button>
        </div>

        <div>
          <div className="mb-1 text-xs font-semibold text-slate-400">PUBLISH</div>
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-100">
            My Projects
          </button>
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-100">
            Pricing
          </button>
        </div>
      </nav>
    </aside>
  );
};

export default Sidebar;
