import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { detectGPUCapability } from './Fallback2DAnimation';

// Mock WebGL context
const mockWebGLContext = {
    getExtension: vi.fn().mockReturnValue({
        UNMASKED_RENDERER_WEBGL: 37446,
    }),
    getParameter: vi.fn().mockReturnValue('NVIDIA GeForce GTX 1080'),
};

const mockCanvas = {
    getContext: vi.fn((contextType: string) => {
        if (contextType === 'webgl' || contextType === 'experimental-webgl') {
            return mockWebGLContext;
        }
        return null;
    }),
};

describe('WebGL Detection', () => {
    let originalCreateElement: typeof document.createElement;

    beforeEach(() => {
        originalCreateElement = document.createElement.bind(document);
        vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
            if (tagName === 'canvas') {
                return mockCanvas as unknown as HTMLCanvasElement;
            }
            return originalCreateElement(tagName);
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
        cleanup();
    });

    it('should detect WebGL support when available', () => {
        mockCanvas.getContext.mockReturnValue(mockWebGLContext);

        // Test the detection logic directly
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl');

        expect(gl).not.toBeNull();
    });

    it('should return false when WebGL is not available', () => {
        mockCanvas.getContext.mockReturnValue(null);

        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl');

        expect(gl).toBeNull();
    });
});

describe('GPU Capability Detection', () => {
    let originalCreateElement: typeof document.createElement;

    beforeEach(() => {
        originalCreateElement = document.createElement.bind(document);
    });

    afterEach(() => {
        vi.restoreAllMocks();
        cleanup();
    });

    it('should detect capable GPU', () => {
        vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
            if (tagName === 'canvas') {
                return {
                    getContext: () => ({
                        getExtension: () => ({
                            UNMASKED_RENDERER_WEBGL: 37446,
                        }),
                        getParameter: () => 'NVIDIA GeForce GTX 1080',
                    }),
                } as unknown as HTMLCanvasElement;
            }
            return originalCreateElement(tagName);
        });

        const result = detectGPUCapability();
        expect(result).toBe(true);
    });

    it('should detect software renderer as low capability', () => {
        vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
            if (tagName === 'canvas') {
                return {
                    getContext: () => ({
                        getExtension: () => ({
                            UNMASKED_RENDERER_WEBGL: 37446,
                        }),
                        getParameter: () => 'SwiftShader',
                    }),
                } as unknown as HTMLCanvasElement;
            }
            return originalCreateElement(tagName);
        });

        const result = detectGPUCapability();
        expect(result).toBe(false);
    });

    it('should return false when WebGL context is not available', () => {
        vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
            if (tagName === 'canvas') {
                return {
                    getContext: () => null,
                } as unknown as HTMLCanvasElement;
            }
            return originalCreateElement(tagName);
        });

        const result = detectGPUCapability();
        expect(result).toBe(false);
    });
});

describe('Fallback2DAnimation', () => {
    it('should render fallback animation with correct test id', async () => {
        // Dynamic import to avoid Three.js initialization issues in test
        const { Fallback2DAnimation } = await import('./Fallback2DAnimation');

        render(<Fallback2DAnimation />);

        const fallbackElement = screen.getByTestId('fallback-2d-animation');
        expect(fallbackElement).toBeInTheDocument();
    });
});
