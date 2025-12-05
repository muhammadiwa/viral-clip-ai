import { useEffect, RefObject } from "react";

/**
 * Custom hook that detects clicks outside of a referenced element.
 * Useful for closing dropdowns, modals, and other overlay components.
 *
 * @param ref - React ref object pointing to the element to monitor
 * @param handler - Callback function to execute when a click outside is detected
 *
 * Requirements: 2.4, 4.4
 * - WHEN a user clicks outside the profile dropdown THEN the Navbar SHALL close the dropdown menu
 * - WHEN a user clicks outside the mobile drawer or clicks a navigation link THEN the Navbar SHALL close the mobile drawer
 */
export function useClickOutside<T extends HTMLElement>(
    ref: RefObject<T>,
    handler: () => void
): void {
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent | TouchEvent) => {
            // Do nothing if clicking ref's element or descendent elements
            if (!ref.current || ref.current.contains(event.target as Node)) {
                return;
            }
            handler();
        };

        // Bind the event listeners
        document.addEventListener("mousedown", handleClickOutside);
        document.addEventListener("touchstart", handleClickOutside);

        return () => {
            // Unbind the event listeners on cleanup
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("touchstart", handleClickOutside);
        };
    }, [ref, handler]);
}

export default useClickOutside;
