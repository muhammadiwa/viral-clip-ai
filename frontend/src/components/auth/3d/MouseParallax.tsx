import React, { useRef, useEffect, createContext, useContext, useState, ReactNode } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

// Context for sharing mouse position across components
interface MouseContextValue {
    mouseX: number;
    mouseY: number;
    normalizedX: number;
    normalizedY: number;
}

const MouseContext = createContext<MouseContextValue>({
    mouseX: 0,
    mouseY: 0,
    normalizedX: 0,
    normalizedY: 0,
});

export const useMousePosition = () => useContext(MouseContext);

// Provider component for mouse tracking
interface MouseProviderProps {
    children: ReactNode;
    containerRef?: React.RefObject<HTMLDivElement>;
}

export const MouseProvider: React.FC<MouseProviderProps> = ({ children, containerRef }) => {
    const [mousePosition, setMousePosition] = useState<MouseContextValue>({
        mouseX: 0,
        mouseY: 0,
        normalizedX: 0,
        normalizedY: 0,
    });

    useEffect(() => {
        const handleMouseMove = (event: MouseEvent) => {
            const container = containerRef?.current || document.body;
            const rect = container.getBoundingClientRect();

            const mouseX = event.clientX - rect.left;
            const mouseY = event.clientY - rect.top;

            // Normalize to -1 to 1 range
            const normalizedX = (mouseX / rect.width) * 2 - 1;
            const normalizedY = -((mouseY / rect.height) * 2 - 1);

            setMousePosition({
                mouseX,
                mouseY,
                normalizedX,
                normalizedY,
            });
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, [containerRef]);

    return (
        <MouseContext.Provider value={mousePosition}>
            {children}
        </MouseContext.Provider>
    );
};

// Hook for applying parallax effect to a group
interface UseParallaxOptions {
    intensity?: number;
    smoothing?: number;
}

export const useParallax = (options: UseParallaxOptions = {}) => {
    const { intensity = 0.5, smoothing = 0.1 } = options;
    const groupRef = useRef<THREE.Group>(null);
    const targetRotation = useRef({ x: 0, y: 0 });
    const { mouse } = useThree();

    useFrame(() => {
        if (groupRef.current) {
            // Calculate target rotation based on mouse position
            targetRotation.current.x = mouse.y * intensity * 0.3;
            targetRotation.current.y = mouse.x * intensity * 0.3;

            // Smooth interpolation
            groupRef.current.rotation.x += (targetRotation.current.x - groupRef.current.rotation.x) * smoothing;
            groupRef.current.rotation.y += (targetRotation.current.y - groupRef.current.rotation.y) * smoothing;
        }
    });

    return groupRef;
};

// Wrapper component that applies parallax to its children
interface ParallaxGroupProps {
    children: ReactNode;
    intensity?: number;
    smoothing?: number;
}

export const ParallaxGroup: React.FC<ParallaxGroupProps> = ({
    children,
    intensity = 0.5,
    smoothing = 0.1,
}) => {
    const groupRef = useParallax({ intensity, smoothing });

    return (
        <group ref={groupRef}>
            {children}
        </group>
    );
};

// Camera parallax effect
interface CameraParallaxProps {
    intensity?: number;
    smoothing?: number;
}

export const CameraParallax: React.FC<CameraParallaxProps> = ({
    intensity = 0.3,
    smoothing = 0.05,
}) => {
    const { camera, mouse } = useThree();
    const targetPosition = useRef({ x: 0, y: 0 });
    const initialPosition = useRef({ x: camera.position.x, y: camera.position.y });

    useFrame(() => {
        // Calculate target position based on mouse
        targetPosition.current.x = initialPosition.current.x + mouse.x * intensity;
        targetPosition.current.y = initialPosition.current.y + mouse.y * intensity;

        // Smooth interpolation
        camera.position.x += (targetPosition.current.x - camera.position.x) * smoothing;
        camera.position.y += (targetPosition.current.y - camera.position.y) * smoothing;

        // Always look at center
        camera.lookAt(0, 0, 0);
    });

    return null;
};

export default ParallaxGroup;
