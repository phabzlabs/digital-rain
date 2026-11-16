#version 330
uniform vec4 u_rect;   // x, y, w, h in px, top-left origin
uniform vec2 u_res;
out vec2 uv;
void main() {
    vec2 corner = vec2(gl_VertexID & 1, gl_VertexID >> 1);
    uv = corner;
    vec2 px = u_rect.xy + corner * u_rect.zw;
    gl_Position = vec4(px.x / u_res.x * 2.0 - 1.0, 1.0 - px.y / u_res.y * 2.0, 0.0, 1.0);
}
