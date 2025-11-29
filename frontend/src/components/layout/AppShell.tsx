import React from "react";
import Sidebar from "./Sidebar";

const AppShell: React.FC<React.PropsWithChildren> = ({ children }) => {
  return (
    <div className="flex h-screen bg-[#fdf7f4]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
    </div>
  );
};

export default AppShell;
