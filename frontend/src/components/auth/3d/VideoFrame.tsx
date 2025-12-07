import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface VideoFrameProps {
    position?: [number, number, number];
    scale?: number;
    floatSpeed?: number;
    floatAmplitude?: number;
    rotationOffset?: number;
}

export const VideoFrame: React.FC<VideoFrameProps> = ({
    position = [0, 0, 0],
    scale = 1,
    floatSpeed = 1,
    floatAmplitude = 0.3,
    rotationOffset = 0,
}) => {
    const groupRef = useRef<THREE.Group>(null);
    const initialY = position[1];
    const timeOffset = useMemo(() => Math.random() * Math.PI * 2, []);

    // Create frame geometry with border
    const frameGeometry = useMemo(() => {
        const shape = new THREE.Shape();
        const width = 1.6;
        const height = 0.9;
        const borderWidth = 0.08;
        const cornerRadius = 0.05;

        // Outer rectangle with rounded corners
        shape.moveTo(-width / 2 + cornerRadius, -height / 2);
        shape.lineTo(width / 2 - cornerRadius, -height / 2);
        shape.quadraticCurveTo(width / 2, -height / 2, width / 2, -height / 2 + cornerRadius);
        shape.lineTo(width / 2, height / 2 - cornerRadius);
        shape.quadraticCurveTo(width / 2, height / 2, width / 2 - cornerRadius, height / 2);
        shape.lineTo(-width / 2 + cornerRadius, height / 2);
        shape.quadraticCurveTo(-width / 2, height / 2, -width / 2, height / 2 - cornerRadius);
        shape.lineTo(-width / 2, -height / 2 + cornerRadius);
        shape.quadraticCurveTo(-width / 2, -height / 2, -width / 2 + cornerRadius, -height / 2);

        // Inner cutout (the "screen" area)
        const innerWidth = width - borderWidth * 2;
        const innerHeight = height - borderWidth * 2;
        const innerCornerRadius = 0.03;

        const hole = new THREE.Path();
        hole.moveTo(-innerWidth / 2 + innerCornerRadius, -innerHeight / 2);
        hole.lineTo(innerWidth / 2 - innerCornerRadius, -innerHeight / 2);
        hole.quadraticCurveTo(innerWidth / 2, -innerHeight / 2, innerWidth / 2, -innerHeight / 2 + innerCornerRadius);
        hole.lineTo(innerWidth / 2, innerHeight / 2 - innerCornerRadius);
        hole.quadraticCurveTo(innerWidth / 2, innerHeight / 2, innerWidth / 2 - innerCornerRadius, innerHeight / 2);
        hole.lineTo(-innerWidth / 2 + innerCornerRadius, innerHeight / 2);
        hole.quadraticCurveTo(-innerWidth / 2, innerHeight / 2, -innerWidth / 2, innerHeight / 2 - innerCornerRadius);
        hole.lineTo(-innerWidth / 2, -innerHeight / 2 + innerCornerRadius);
        hole.quadraticCurveTo(-innerWidth / 2, -innerHeight / 2, -innerWidth / 2 + innerCornerRadius, -innerHeight / 2);

        shape.holes.push(hole);

        return new THREE.ExtrudeGeometry(shape, {
            depth: 0.05,
            bevelEnabled: true,
            bevelThickness: 0.01,
            bevelSize: 0.01,
            bevelSegments: 2,
        });
    }, []);

    // Screen geometry (inner area)
    const screenGeometry = useMemo(() => {
        return new THREE.PlaneGeometry(1.44, 0.74);
    }, []);

    // Materials
    const frameMaterial = useMemo(() => {
        return new THREE.MeshStandardMaterial({
            color: '#2d2d44',
            metalness: 0.7,
            roughness: 0.3,
        });
    }, []);

    const screenMaterial = useMemo(() => {
        return new THREE.MeshStandardMaterial({
            color: '#0a0a15',
            metalness: 0.1,
            roughness: 0.8,
            emissive: '#ff6a00',
            emissiveIntensity: 0.05,
        });
    }, []);

    // Floating animation
    useFrame(({ clock }) => {
        if (groupRef.current) {
            const time = clock.getElapsedTime() * floatSpeed + timeOffset;
            groupRef.current.position.y = initialY + Math.sin(time) * floatAmplitude;
            groupRef.current.rotation.y = Math.sin(time * 0.5) * 0.1 + rotationOffset;
            groupRef.current.rotation.x = Math.cos(time * 0.3) * 0.05;
        }
    });

    return (
        <group ref={groupRef} position={position} scale={scale}>
            {/* Frame border */}
            <mesh geometry={frameGeometry} material={frameMaterial} />

            {/* Screen surface */}
            <mesh geometry={screenGeometry} material={screenMaterial} position={[0, 0, 0.03]} />

            {/* Play button icon */}
            <mesh position={[0, 0, 0.04]}>
                <circleGeometry args={[0.15, 32]} />
                <meshStandardMaterial
                    color="#ff6a00"
                    transparent
                    opacity={0.8}
                    emissive="#ff6a00"
                    emissiveIntensity={0.3}
                />
            </mesh>
            <mesh position={[0.03, 0, 0.05]} rotation={[0, 0, -Math.PI / 2]}>
                <coneGeometry args={[0.08, 0.12, 3]} />
                <meshStandardMaterial color="#ffffff" />
            </mesh>
        </group>
    );
};

// Multiple floating frames component
interface FloatingVideoFramesProps {
    count?: number;
}

export const FloatingVideoFrames: React.FC<FloatingVideoFramesProps> = ({ count = 4 }) => {
    const frames = useMemo(() => {
        const positions: {
            position: [number, number, number];
            scale: number;
            floatSpeed: number;
            rotationOffset: number;
        }[] = [
                { position: [-2.5, 1.5, -2], scale: 0.6, floatSpeed: 0.8, rotationOffset: 0.3 },
                { position: [2.8, -1, -3], scale: 0.5, floatSpeed: 1.2, rotationOffset: -0.2 },
                { position: [-1.5, -1.8, -1.5], scale: 0.45, floatSpeed: 1, rotationOffset: 0.1 },
                { position: [2, 2, -2.5], scale: 0.55, floatSpeed: 0.9, rotationOffset: -0.4 },
            ];
        return positions.slice(0, count);
    }, [count]);

    return (
        <>
            {frames.map((frame, index) => (
                <VideoFrame
                    key={`video-frame-${index}`}
                    position={frame.position}
                    scale={frame.scale}
                    floatSpeed={frame.floatSpeed}
                    rotationOffset={frame.rotationOffset}
                />
            ))}
        </>
    );
};

export default VideoFrame;
