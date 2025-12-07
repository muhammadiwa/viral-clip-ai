import React, { Suspense, useEffect, useState, useRef, useCallback } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { Fallback2DAnimation, detectGPUCapability } from './Fallback2DAnimation';
import { FilmReel } from './FilmReel';
import { FloatingVideoFrames } from './VideoFrame';
import { GlowingParticles } from './ParticleSystem';
import { ParallaxGroup, CameraParallax } from './MouseParallax';

interface Auth3DSceneProps {
    isInteractive?: boolean;
    fallbackMode?: boolean;
}

// WebGL detection utility
const detectWebGLSupport = (): boolean => {
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        return gl !== null && gl !== undefined;
    } catch {
        return false;
    }
};

// Loading fallback for Suspense
const LoadingFallback: React.FC = () => (
    <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
);

// Cleanup component that disposes resources on unmount
const ResourceCleanup: React.FC = () => {
    const { gl, scene } = useThree();

    useEffect(() => {
        return () => {
            // Dispose all geometries, materials, and textures in the scene
            scene.traverse((object) => {
                if (object instanceof THREE.Mesh) {
                    if (object.geometry) {
                        object.geometry.dispose();
                    }
                    if (object.material) {
                        if (Array.isArray(object.material)) {
                            object.material.forEach((material) => disposeMaterial(material));
                        } else {
                            disposeMaterial(object.material);
                        }
                    }
                }
                if (object instanceof THREE.Points) {
                    if (object.geometry) {
                        object.geometry.dispose();
                    }
                    if (object.material) {
                        if (Array.isArray(object.material)) {
                            object.material.forEach((material) => disposeMaterial(material));
                        } else {
                            disposeMaterial(object.material);
                        }
                    }
                }
            });

            // Clear the scene
            while (scene.children.length > 0) {
                scene.remove(scene.children[0]);
            }

            // Dispose the renderer
            gl.dispose();
            gl.forceContextLoss();
        };
    }, [gl, scene]);

    return null;
};

// Helper function to dispose materials
const disposeMaterial = (material: THREE.Material) => {
    material.dispose();

    // Dispose textures if present
    const mat = material as THREE.MeshStandardMaterial;
    if (mat.map) mat.map.dispose();
    if (mat.normalMap) mat.normalMap.dispose();
    if (mat.roughnessMap) mat.roughnessMap.dispose();
    if (mat.metalnessMap) mat.metalnessMap.dispose();
    if (mat.emissiveMap) mat.emissiveMap.dispose();
    if (mat.aoMap) mat.aoMap.dispose();
};

export const Auth3DScene: React.FC<Auth3DSceneProps> = ({
    isInteractive = true,
    fallbackMode = false,
}) => {
    const [webGLSupported, setWebGLSupported] = useState<boolean | null>(null);
    const [gpuCapable, setGpuCapable] = useState<boolean | null>(null);
    const [hasError, setHasError] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const animationFrameRef = useRef<number | null>(null);

    useEffect(() => {
        const webglSupported = detectWebGLSupport();
        const gpuOk = detectGPUCapability();
        setWebGLSupported(webglSupported);
        setGpuCapable(gpuOk);
    }, []);

    // Cleanup animation frames on unmount
    useEffect(() => {
        return () => {
            if (animationFrameRef.current !== null) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, []);

    const handleError = useCallback(() => {
        setHasError(true);
    }, []);

    // Show loading state while detecting WebGL
    if (webGLSupported === null || gpuCapable === null) {
        return <LoadingFallback />;
    }

    // Use fallback if WebGL not supported, GPU not capable, forced fallback mode, or error occurred
    if (!webGLSupported || !gpuCapable || fallbackMode || hasError) {
        return <Fallback2DAnimation />;
    }

    return (
        <div
            ref={containerRef}
            className="absolute inset-0 w-full h-full"
            data-testid="auth-3d-scene"
        >
            <Suspense fallback={<LoadingFallback />}>
                <Canvas
                    camera={{ position: [0, 0, 5], fov: 75 }}
                    dpr={[1, 2]}
                    gl={{
                        antialias: true,
                        alpha: true,
                        powerPreference: 'high-performance',
                        failIfMajorPerformanceCaveat: true,
                    }}
                    onCreated={({ gl }) => {
                        gl.setClearColor(0x000000, 0);
                    }}
                    onError={handleError}
                >
                    <ResourceCleanup />
                    <SceneContent isInteractive={isInteractive} />
                </Canvas>
            </Suspense>
        </div>
    );
};

// Scene content with all 3D elements
const SceneContent: React.FC<{ isInteractive: boolean }> = ({ isInteractive }) => {
    return (
        <>
            {/* Lighting */}
            <ambientLight intensity={0.4} />
            <pointLight position={[10, 10, 10]} intensity={1} color="#ffffff" />
            <pointLight position={[-10, -10, 5]} intensity={0.5} color="#ff6a00" />

            {/* Camera parallax effect */}
            {isInteractive && <CameraParallax intensity={0.2} smoothing={0.03} />}

            {/* Main content with parallax */}
            <ParallaxGroup intensity={isInteractive ? 0.3 : 0} smoothing={0.05}>
                {/* Central film reel */}
                <FilmReel position={[0, 0, -1]} scale={0.8} rotationSpeed={0.3} />

                {/* Floating video frames */}
                <FloatingVideoFrames count={4} />
            </ParallaxGroup>

            {/* Particles (not affected by parallax for depth effect) */}
            <GlowingParticles />
        </>
    );
};

export default Auth3DScene;
