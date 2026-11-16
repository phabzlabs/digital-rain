// Image layer: a full-resolution per-pixel layer, independent of the glyph grid. The scene
// pass writes, per rain cell, whether the first rain head after the picture's start has
// landed on it (B: picture 0, A: picture 1); this adds fine picture detail, mapped through
// the palette, wherever that holds. Shared by final.frag and scan.frag, which must define
// img_cover and palette_at (common.glsl) before it.
uniform int u_img_on;
uniform sampler2D u_imgrev;      // render-size scene texture: B / A hold the reveal flags
uniform sampler2D u_img0;        // picture, RGBA: R lifted luminance, G open background, B tone, A dark open; mipmapped
uniform sampler2D u_img1;
uniform vec2 u_img_size0;        // picture size, for the aspect-fill crop
uniform vec2 u_img_size1;
uniform vec2 u_img_soft;         // reveal softening radius, in uv units (about half a rain cell)
uniform vec3 u_img_amt;          // strength, gain, gamma
uniform vec4 u_ipal[8];
uniform int u_inpal;
uniform vec4 u_irect[%(MAX_MON)d];   // monitor rectangles, display px, top-left origin
uniform int u_imon;

// 3x3 Sobel gradient magnitude of the picture's luminance around uv, at full resolution.
float sobel_edge(sampler2D tex, vec2 uv, vec2 texel) {
    float a = textureLod(tex, uv + vec2(-texel.x, -texel.y), 0.0).r;
    float b = textureLod(tex, uv + vec2(0.0, -texel.y), 0.0).r;
    float c = textureLod(tex, uv + vec2(texel.x, -texel.y), 0.0).r;
    float d = textureLod(tex, uv + vec2(-texel.x, 0.0), 0.0).r;
    float f = textureLod(tex, uv + vec2(texel.x, 0.0), 0.0).r;
    float g = textureLod(tex, uv + vec2(-texel.x, texel.y), 0.0).r;
    float h = textureLod(tex, uv + vec2(0.0, texel.y), 0.0).r;
    float i = textureLod(tex, uv + vec2(texel.x, texel.y), 0.0).r;
    return length(vec2((c + 2.0 * f + i) - (a + 2.0 * d + g), (g + 2.0 * h + i) - (a + 2.0 * b + c)));
}

// p: display px (top-left origin); ruv: uv into the render-size reveal texture.
vec3 image_layer(vec2 p, vec2 ruv) {
    if (u_img_on == 0) return vec3(0.0);
    vec4 mr = vec4(0.0, 0.0, 1.0, 1.0);
    for (int m = 0; m < u_imon; m++) {
        vec4 r = u_irect[m];
        if (p.x >= r.x && p.x < r.x + r.z && p.y >= r.y && p.y < r.y + r.w) { mr = r; break; }
    }
    vec2 rv = vec2(0.0);
    for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++)
            rv += texture(u_imgrev, ruv + vec2(float(i), float(j)) * u_img_soft).ba;
    rv /= 9.0;
    if (rv.x + rv.y <= 0.0) return vec3(0.0);
    vec2 st = (p - mr.xy) / mr.zw;
    // Fine detail at display resolution: a little of the picture plus its edges, under the
    // glyphs, which carry the shapes at cell scale.
    float l = 0.0, e = 0.0;
    if (rv.x > 0.0) {
        vec2 c0 = img_cover(st, u_img_size0, mr.zw);
        e += rv.x * sobel_edge(u_img0, c0, 1.0 / u_img_size0);
        l += rv.x * texture(u_img0, c0).r;
    }
    if (rv.y > 0.0) {
        vec2 c1 = img_cover(st, u_img_size1, mr.zw);
        e += rv.y * sobel_edge(u_img1, c1, 1.0 / u_img_size1);
        l += rv.y * texture(u_img1, c1).r;
    }
    float v = clamp(l * u_img_amt.y * 0.35 + e * 1.2, 0.0, 1.0);
    v = pow(v, u_img_amt.z);
    return palette_at(u_ipal, u_inpal, v) * (u_img_amt.x * smoothstep(0.0, 0.06, v));
}
