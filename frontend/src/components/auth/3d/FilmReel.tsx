import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface FilmReelProps {
    position?: [number, number, number];
    scale?: number;
    rotationSpeed?: number;
}

export const FilmReel: React.FC<FilmReelProps> = ({
    position = [0, 0, 0],
    scale = 1,
    rotationSpeed = 0.5,
}) => {
    const groupRef = useRef<THREE.Group>(null);

    // Create film reel geometry procedurally
    const { outerRing, innerRing, spokes, holes } = useMemo(() => {
        // Outer ring (torus)
        const outerRingGeometry = new THREE.TorusGeometry(1.5, 0.15, 16, 64);

        // Inner ring (smaller torus)
        const innerRingGeometry = new THREE.TorusGeometry(0.5, 0.1, 16, 32);

        // Spokes connecting inner and outer rings
        const spokeGeometry = new THREE.CylinderGeometry(0.05, 0.05, 1, 8);

        // Film holes (small cylinders around the outer edge)
        const holeGeometry = new THREE.CylinderGeometry(0.08, 0.08, 0.2, 8);

        return {
            outerRing: outerRingGeometry,
            innerRing: innerRingGeometry,
            spokes: spokeGeometry,
            holes: holeGeometry,
        };
    }, []);

    // Materials
    const reelMaterial = useMemo(() => {
        return new THREE.MeshStandardMaterial({
            color: '#1a1a2e',
            metalness: 0.8,
            roughness: 0.2,
        });
    }, []);

    const accentMaterial = useMemo(() => {
        return new THREE.MeshStandardMaterial({
            color: '#ff6a00',
            metalness: 0.6,
            roughness: 0.3,
            emissive: '#ff6a00',
            emissiveIntensity: 0.2,
        });
    }, []);

    // Animation
    useFrame((_, delta) => {
        if (groupRef.current) {
            groupRef.current.rotation.z += delta * rotationSpeed;
        }
    });

    // Generate spoke positions (6 spokes)
    const spokePositions = useMemo(() => {
        const positions: { position: [number, number, number]; rotation: number }[] = [];
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            positions.push({
                position: [Math.cos(angle) * 1, Math.sin(angle) * 1, 0],
                rotation: angle,
            });
        }
        return positions;
    }, []);

    // Generate hole positions around the outer ring
    const holePositions = useMemo(() => {
        const positions: [number, number, number][] = [];
        const numHoles = 24;
        for (let i = 0; i < numHoles; i++) {
            const angle = (i / numHoles) * Math.PI * 2;
            positions.push([Math.cos(angle) * 1.5, Math.sin(angle) * 1.5, 0]);
        }
        return positions;
    }, []);

    return (
        <group ref={groupRef} position={position} scale={scale}>
            {/* Outer ring */}
            <mesh geometry={outerRing} material={reelMaterial} />

            {/* Inner ring */}
            <mesh geometry={innerRing} material={accentMaterial} />

            {/* Center hub */}
            <mesh>
                <cylinderGeometry args={[0.3, 0.3, 0.15, 32]} />
                <meshStandardMaterial color="#ff6a00" metalness={0.7} roughness={0.3} />
            </mesh>

            {/* Spokes */}
            {spokePositions.map((spoke, index) => (
                <mesh
                    key={`spoke-${index}`}
                    position={spoke.position}
                    rotation={[0, 0, spoke.rotation + Math.PI / 2]}
                    geometry={spokes}
                    material={reelMaterial}
                />
            ))}

            {/* Film holes */}
            {holePositions.map((pos, index) => (
                <mesh
                    key={`hole-${index}`}
                    position={pos}
                    rotation={[Math.PI / 2, 0, 0]}
                    geometry={holes}
                    material={accentMaterial}
                />
            ))}
        </group>
    );
};

export default FilmReel;
