// Display-resolution finish for the FSR path, run on every sharpened pixel by fsr.py's RCAS
// pass (post_process): picture detail, flicker gain, ink grain and dots, scanlines and the
// 8-bit dither. With FSR the frame is composed at render resolution and upscaled first, so
// the scanlines and flicker stay one real pixel row thick. Needs COMMON, IMG_GLSL and
// INK_GRAIN substituted in, and reads the EASU texture u_src for its size.
uniform float u_gain;
uniform float u_scan;
uniform float u_field;
// film grain on the ink at display resolution
uniform float u_grain_ink;
// palette floor: the background carries no ink grain
uniform vec3 u_floor;
uniform float u_seed;
// ink dot pitch (display px at dpi 1), strength, x share (strength 0: off)
uniform vec3 u_dots;
// monitor rectangles, display px, bottom-left origin
uniform vec4 u_drect[%(MAX_MON)d];
// monitor dpi (the dot pitch scales per monitor)
uniform float u_ddpi[%(MAX_MON)d];
uniform int u_dn;
%(COMMON)s
%(IMG_GLSL)s
%(INK_GRAIN)s
vec3 post_process(vec3 c) {
    if (u_img_on != 0) {
        vec2 sz = vec2(textureSize(u_src, 0));
        c = min(c + image_layer(vec2(gl_FragCoord.x, sz.y - gl_FragCoord.y), gl_FragCoord.xy / sz),
                vec3(1.0));
    }
    c *= u_gain;
    if (u_grain_ink > 0.0)
        c = ink_grain(c, u_floor, gl_FragCoord.xy + u_seed);
    if (u_dots.y > 0.0) {
        for (int m = 0; m < u_dn; m++) {
            vec4 r = u_drect[m];
            if (gl_FragCoord.x >= r.x && gl_FragCoord.x < r.x + r.z
                && gl_FragCoord.y >= r.y && gl_FragCoord.y < r.y + r.w) {
                c = ink_dots(c, u_floor, gl_FragCoord.xy, u_dots.x * u_ddpi[m], u_dots.y, u_dots.z);
                break;
            }
        }
    }
    if (u_scan > 0.0 && mod(floor(gl_FragCoord.y) + u_field, 2.0) < 1.0)
        c *= 1.0 - u_scan;
    // dither the 8-bit output
    c += (hash12(gl_FragCoord.xy) - 0.5) / 255.0;
    return c;
}
