#version 330
uniform sampler2D u_tex;
uniform vec2 u_dir;   // texel step along the blur axis
in vec2 uv;
out vec4 o_col;
void main() {
    vec3 c = texture(u_tex, uv).rgb * 0.2270270;
    c += (texture(u_tex, uv + u_dir * 1.3846154).rgb
        + texture(u_tex, uv - u_dir * 1.3846154).rgb) * 0.3162162;
    c += (texture(u_tex, uv + u_dir * 3.2307692).rgb
        + texture(u_tex, uv - u_dir * 3.2307692).rgb) * 0.0702703;
    o_col = vec4(c, 1.0);
}
