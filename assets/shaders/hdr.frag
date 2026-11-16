#version 330
// HDR output pass: the finished display-referred (sRGB encoded) frame becomes
// linear light for a float16 back buffer. Windows reads it as scRGB (1.0 = 80
// nits), macOS as extended linear sRGB (1.0 = SDR white). Dim cells (below
// the ramp start) are the SDR picture at the user's SDR white level; brighter
// cells, mid-bright trail and heads alike, are expanded towards the headroom.
uniform sampler2D u_tex;
uniform float u_white;      // output value of SDR white (Windows: SDR nits / 80, Mac: 1)
uniform float u_headroom;   // peak / SDR white, at least 1
in vec2 uv;
out vec4 o_col;
vec3 to_linear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
}
void main() {
    vec3 lin = to_linear(clamp(texture(u_tex, uv).rgb, 0.0, 1.0));
    float m = max(lin.r, max(lin.g, lin.b));
    // dim cells stay at SDR white, mid cells lift, heads reach the peak
    float k = smoothstep(0.12, 0.8, m);
    float boost = 1.0 + (u_headroom - 1.0) * pow(k, 1.3);
    o_col = vec4(lin * boost * u_white, 1.0);
}
