#version 330
uniform sampler2D u_tex;
uniform int u_use_tex;
uniform float u_reveal;   // 0..1 fraction of the width that is typed so far
uniform vec4 u_color;
in vec2 uv;
out vec4 o_col;
void main() {
    if (u_use_tex == 1) {
        if (uv.x > u_reveal) discard;
        float g = texture(u_tex, uv).r;
        o_col = vec4(u_color.rgb * g * u_color.a, 1.0);
    } else {
        o_col = u_color;
    }
}
