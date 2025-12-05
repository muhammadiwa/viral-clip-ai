import React from "react";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

/**
 * Main application shell layout component.
 * Integrates Navbar at top and Sidebar with main content area.
 *
 * Requirements: 1.1, 1.2
 * - WHEN a user loads any page THEN the Navbar SHALL display at the top of the viewport with fixed positioning
 * - WHEN a user scrolls down the page THEN the Navbar SHALL remain visible at the top of the viewport
 */
const AppShell: React.FC<React.PropsWithChildren> = ({ children }) => {
  return (
    <div className="min-h-screen bg-[#fdf7f4] dark:bg-slate-900 transition-colors duration-300">
      {/* Fixed Sidebar */}
      <Sidebar />

      {/* Fixed Navbar at top - already has left-64 offset */}
      <Navbar />

      {/* Main content area - offset for sidebar and navbar (72px + 24px spacing) */}
      <main className="ml-64 pt-[96px] px-8 pb-8 min-h-screen transition-colors duration-300">
        {children}
      </main>
    </div>
  );
};

export default AppShell;
