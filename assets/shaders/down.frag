#version 330
uniform sampler2D u_tex;
uniform vec2 u_texel;
uniform float u_thresh;   // film high-pass on brightness, 0 = off
in vec2 uv;
out vec4 o_col;
void main() {   // 4 bilinear taps = a 4x4 box average
    vec3 c = texture(u_tex, uv + u_texel * vec2(-1.0, -1.0)).rgb
           + texture(u_tex, uv + u_texel * vec2( 1.0, -1.0)).rgb
           + texture(u_tex, uv + u_texel * vec2(-1.0,  1.0)).rgb
           + texture(u_tex, uv + u_texel * vec2( 1.0,  1.0)).rgb;
    c *= 0.25;
    if (u_thresh > 0.0 && max(c.r, c.g) < u_thresh) c = vec3(0.0);
    o_col = vec4(c, 1.0);
}
