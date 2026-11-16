#version 330
uniform sampler2D u_scene;
uniform sampler2D u_bloom1;
uniform sampler2D u_bloom2;
uniform vec2 u_res;
uniform float u_g1;
uniform float u_g2;
uniform float u_scan;
uniform float u_field;
uniform float u_vig;
uniform float u_gain;
uniform int u_nmon;
uniform vec4 u_mon[%(MAX_MON)d];
uniform int u_film;
uniform vec4 u_pal[8];     // palette stops: rgb, position in w
uniform int u_npal;
uniform vec3 u_cursor;
uniform float u_grain;
uniform float u_toe;      // palette toe: brightness below this eases to the floor (0: off)
uniform float u_seed;
uniform sampler2D u_pyr1;  // bloom pyramid, 1/2 .. 1/16 render size (units 3 to 6)
uniform sampler2D u_pyr2;
uniform sampler2D u_pyr3;
uniform sampler2D u_pyr4;
uniform vec4 u_wr;         // pyramid weights on brightness (R)
uniform vec4 u_wg;         // pyramid weights on the leader flag (G)
uniform int u_pyr_on;
uniform float u_lcore;     // leader core widening
uniform float u_lglow;     // share of the leader halo painted as cursor-coloured light (0: off)
uniform float u_lcap;      // cap on the leader halo light (0: off)
uniform int u_ink_in_final;
uniform float u_grain_ink;
// ink dot pitch (display px at dpi 1), strength, x share (strength 0: off)
uniform vec3 u_dots;
uniform float u_ddpi[%(MAX_MON)d];   // monitor dpi (the dot pitch scales per monitor)
in vec2 uv;
out vec4 o_col;
%(COMMON)s
%(IMG_GLSL)s
%(INK_GRAIN)s
vec3 palette(float x) {
    // the toe pulls the faint bloom haze between streams down to the palette floor;
    // brightness at or above u_toe is unchanged
    if (u_toe > 0.0) x *= smoothstep(0.0, u_toe, x);
    return palette_at(u_pal, u_npal, x);
}
void main() {
    vec3 c;
    if (u_pyr_on == 1 && u_film == 1) {
        // Bloom pyramid and halation summed into brightness, then the palette; the leader
        // core is the cursor colour itself.
        vec3 s = texture(u_scene, uv).rgb;
        vec3 p1 = texture(u_pyr1, uv).rgb, p2 = texture(u_pyr2, uv).rgb;
        vec3 p3 = texture(u_pyr3, uv).rgb, p4 = texture(u_pyr4, uv).rgb;
        float x = s.r + dot(u_wr, vec4(p1.r, p2.r, p3.r, p4.r))
                      + dot(u_wg, vec4(p1.g, p2.g, p3.g, p4.g))
                      - hash12(gl_FragCoord.xy + u_seed) * u_grain;
        float core = clamp(s.g * u_lcore, 0.0, 1.0);
        if (u_lglow > 0.0) {
            float wg = dot(u_wg, vec4(p1.g, p2.g, p3.g, p4.g));
            c = mix(palette(clamp(x - u_lglow * wg, 0.0, 1.0)), u_cursor, core);
            if (u_lcap > 0.0) wg = min(wg, u_lcap);
            c = min(c + u_lglow * (1.0 - core) * u_cursor * wg, vec3(1.0));
        } else {
            c = mix(palette(clamp(x, 0.0, 1.0)), u_cursor, core);
        }
        if (u_ink_in_final == 1 && u_grain_ink > 0.0)
            c = ink_grain(c, u_pal[0].rgb, gl_FragCoord.xy + u_seed);
        if (u_ink_in_final == 1 && u_dots.y > 0.0) {   // render px are display px here
            vec2 dp = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
            for (int m = 0; m < u_nmon; m++) {
                vec4 r = u_mon[m];
                if (dp.x >= r.x && dp.x < r.x + r.z && dp.y >= r.y && dp.y < r.y + r.w) {
                    c = ink_dots(c, u_pal[0].rgb, gl_FragCoord.xy, u_dots.x * u_ddpi[m], u_dots.y, u_dots.z);
                    break;
                }
            }
        }
    } else {
        c = texture(u_scene, uv).rgb
          + texture(u_bloom1, uv).rgb * u_g1
          + texture(u_bloom2, uv).rgb * u_g2;
        if (u_film == 1) {   // brightness -> palette after bloom, with grain
            float x = c.r - hash12(gl_FragCoord.xy + u_seed) * u_grain;
            c = min(palette(clamp(x, 0.0, 1.0)) + u_cursor * c.g, vec3(1.0));
        }
    }
    vec2 p = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
    if (u_img_on != 0 && u_film == 1) c = min(c + image_layer(p, uv), vec3(1.0));
    for (int m = 0; m < u_nmon; m++) {
        vec4 r = u_mon[m];
        if (p.x >= r.x && p.x < r.x + r.z && p.y >= r.y && p.y < r.y + r.w) {
            vec2 d = ((p - r.xy) / r.zw - 0.5) * 2.0;
            c *= 1.0 - u_vig * smoothstep(0.35, 1.45, length(d));
            break;
        }
    }
    c *= u_gain;
    if (u_scan > 0.0 && mod(floor(gl_FragCoord.y) + u_field, 2.0) < 1.0)
        c *= 1.0 - u_scan;
    o_col = vec4(c, 1.0);
}
