Create a terminal-based rotating ASCII Earth renderer for Python.

Requirements:

- Pure Python
- Runs inside CLI / terminal
- Real-time animation loop
- Software-rendered sphere (not sprite rotation)
- Uses mathematical 3D sphere projection like donut.c
- Smooth continuous X/Y rotation
- Simulated depth buffer (z-buffer)
- ASCII luminance shading using:
  .,-~:;=!*#$@

Earth-specific:

- Sphere surface maps continents/oceans procedurally
- Continents slightly brighter than oceans
- Optional cloud layer rotation at different speed
- Earth axis tilt (~23.5°)
- Day/night shading from directional light source
- Globe should look volumetric, not flat ASCII image
- Visible curvature and realistic spherical lighting

Rendering:

- Clears and redraws in-place using ANSI escape sequences
- 60+ FPS if possible
- Adaptive terminal sizing
- Centered render
- No external graphics libraries
- No pygame
- No image assets
- No pre-rendered frames

Code architecture:

- Modular functions:
  - rotation matrices
  - sphere point generation
  - projection
  - z-buffer
  - brightness-to-char mapping
  - earth texture sampling
  - terminal drawing loop

Output style:

- Similar aesthetic to Andy Sloane’s donut.c
- Dense ASCII 3D shading
- Smooth polished motion
- Looks like a real rotating globe in monochrome terminal

Add:

- ESC key exits
- Adjustable speed
- Configurable radius
- Optional stars background

Return complete executable Python file only.