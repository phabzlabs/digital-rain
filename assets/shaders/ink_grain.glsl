// Ink effects on the film palette. The host shader must define hash12 (common.glsl) and
// u_grain_ink before including this.

// Multiplicative film grain on the ink, about the palette floor `fl` (the background carries
// none). The sum of three hashes, centred and scaled to a standard deviation of exactly 1.
vec3 ink_grain(vec3 c, vec3 fl, vec2 p) {
    float n = (hash12(p + vec2(17.31, 41.73)) + hash12(p + vec2(73.19, 5.97))
             + hash12(p + vec2(29.71, 97.37)) - 1.5) * 2.0;
    return fl + max(c - fl, vec3(0.0)) * (1.0 + u_grain_ink * n);
}

// Static dot mask on the ink at display resolution (look key ink_dots): pitch in display px,
// strength, and the x share. Near-white (the leaders) is spared; the palette floor is untouched.
vec3 ink_dots(vec3 c, vec3 fl, vec2 p, float pitch, float strength, float xs) {
    const float TAU = 6.28318531;
    float cy = 0.5 + 0.5 * cos(TAU * p.y / pitch);
    float cx = 0.5 + 0.5 * cos(TAU * p.x / pitch);
    float m = 1.0 - strength * cy * (1.0 - xs + xs * cx);
    m = mix(m, 1.0, smoothstep(0.62, 0.72, min(c.r, min(c.g, c.b))));
    return fl + max(c - fl, vec3(0.0)) * m;
}
