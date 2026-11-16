// Helpers shared by scene.frag, final.frag and scan.frag (substituted in as %(COMMON)s).

// Cheap 2-D hash to [0, 1), used for film grain and output dither.
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// Colour at x (0..1) along `count` palette stops, each rgb with its position in w.
vec3 palette_at(vec4 stops[8], int count, float x) {
    vec3 c = stops[0].rgb;
    for (int i = 1; i < count; i++) {
        float p0 = stops[i - 1].w, p1 = stops[i].w;
        if (x >= p0)
            c = mix(stops[i - 1].rgb, stops[i].rgb, clamp((x - p0) / max(p1 - p0, 1e-5), 0.0, 1.0));
    }
    return c;
}

// Aspect-fill: the monitor point st (0..1) as picture coordinates (0..1), the picture
// scaled to cover the monitor and cropped evenly.
vec2 img_cover(vec2 st, vec2 isize, vec2 mon) {
    float s = (isize.x / isize.y) / (mon.x / mon.y);
    return s > 1.0 ? vec2((st.x - 0.5) / s + 0.5, st.y) : vec2(st.x, (st.y - 0.5) * s + 0.5);
}

// Inverse of img_cover: picture coordinates to monitor coordinates (0..1).
vec2 img_uncover(vec2 ic, vec2 isize, vec2 mon) {
    float s = (isize.x / isize.y) / (mon.x / mon.y);
    return s > 1.0 ? vec2((ic.x - 0.5) * s + 0.5, ic.y) : vec2(ic.x, (ic.y - 0.5) / s + 0.5);
}
