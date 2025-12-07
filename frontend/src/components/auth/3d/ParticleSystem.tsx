import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface ParticleSystemProps {
    count?: number;
    spread?: number;
    color?: string;
    size?: number;
}

export const ParticleSystem: React.FC<ParticleSystemProps> = ({
    count = 100,
    spread = 10,
    color = '#ff6a00',
    size = 0.05,
}) => {
    const pointsRef = useRef<THREE.Points>(null);
    const velocitiesRef = useRef<Float32Array | null>(null);

    // Generate particle positions and velocities
    const { positions, velocities } = useMemo(() => {
        const posArray = new Float32Array(count * 3);
        const velArray = new Float32Array(count * 3);

        for (let i = 0; i < count; i++) {
            const i3 = i * 3;

            // Random positions within spread area
            posArray[i3] = (Math.random() - 0.5) * spread;
            posArray[i3 + 1] = (Math.random() - 0.5) * spread;
            posArray[i3 + 2] = (Math.random() - 0.5) * spread * 0.5 - 2;

            // Random velocities for subtle movement
            velArray[i3] = (Math.random() - 0.5) * 0.01;
            velArray[i3 + 1] = (Math.random() - 0.5) * 0.01 + 0.005; // Slight upward drift
            velArray[i3 + 2] = (Math.random() - 0.5) * 0.005;
        }

        velocitiesRef.current = velArray;
        return { positions: posArray, velocities: velArray };
    }, [count, spread]);

    // Create geometry with positions
    const geometry = useMemo(() => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        return geo;
    }, [positions]);

    // Particle material with glow effect
    const material = useMemo(() => {
        return new THREE.PointsMaterial({
            color: new THREE.Color(color),
            size,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            sizeAttenuation: true,
        });
    }, [color, size]);

    // Animate particles
    useFrame(() => {
        if (pointsRef.current && velocitiesRef.current) {
            const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
            const velocities = velocitiesRef.current;
            const halfSpread = spread / 2;

            for (let i = 0; i < count; i++) {
                const i3 = i * 3;

                // Update positions
                positions[i3] += velocities[i3];
                positions[i3 + 1] += velocities[i3 + 1];
                positions[i3 + 2] += velocities[i3 + 2];

                // Wrap around boundaries
                if (positions[i3] > halfSpread) positions[i3] = -halfSpread;
                if (positions[i3] < -halfSpread) positions[i3] = halfSpread;
                if (positions[i3 + 1] > halfSpread) positions[i3 + 1] = -halfSpread;
                if (positions[i3 + 1] < -halfSpread) positions[i3 + 1] = halfSpread;
                if (positions[i3 + 2] > 0) positions[i3 + 2] = -spread * 0.5;
                if (positions[i3 + 2] < -spread * 0.5) positions[i3 + 2] = 0;
            }

            pointsRef.current.geometry.attributes.position.needsUpdate = true;
        }
    });

    return (
        <points ref={pointsRef} geometry={geometry} material={material} />
    );
};

// Secondary particle layer for depth
export const GlowingParticles: React.FC = () => {
    return (
        <>
            {/* Main particles - primary color */}
            <ParticleSystem
                count={80}
                spread={12}
                color="#ff6a00"
                size={0.04}
            />
            {/* Secondary particles - lighter color, smaller */}
            <ParticleSystem
                count={40}
                spread={10}
                color="#ff9a4d"
                size={0.025}
            />
            {/* Background particles - subtle white */}
            <ParticleSystem
                count={30}
                spread={15}
                color="#ffffff"
                size={0.02}
            />
        </>
    );
};

export default ParticleSystem;
