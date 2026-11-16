#version 330
uniform vec2 u_res;
uniform float u_time;
uniform int u_nmon;
uniform vec4 u_mon[%(MAX_MON)d];       // x, y, w, h  (top-left origin, px)
uniform float u_dpi[%(MAX_MON)d];
uniform int u_nlay;
uniform vec4 u_lay0[%(MAX_LAYERS)d];   // scale, dim, speed, density
uniform vec4 u_lay1[%(MAX_LAYERS)d];   // trail, soft
uniform vec3 u_base;
uniform vec3 u_head;
uniform float u_falloff;
uniform float u_gscale;
uniform sampler2D u_atlas;
uniform vec4 u_atl;                    // cols, rows, margin_x, margin_y (0..1)
uniform int u_nglyph;
uniform sampler2D u_atlas2;            // resurrections tiles, R glyph and G glint (texture unit 4)
uniform vec4 u_atl2;                   // cols, rows, margin_x, margin_y of the second atlas
uniform sampler2D u_atlas3;            // classic tiles with the ink stretched (texture unit 5)
// 0: classic atlas, 1: second atlas, 2: stretched classic atlas
uniform int u_set;
uniform float u_cols;                  // square cells, this many columns (0: classic cell)
uniform float u_glint;                 // glint gain (0: off)
uniform int u_film;                    // 1: film presets (saw model), 0: custom (drop model)
uniform int u_dirmode;                 // 0 down, 1 sideways, 2 diagonal
uniform vec2 u_speed;                  // rows/s range per lane
uniform vec4 u_saw;                    // tooth, contrast, bias, flat
uniform float u_lead;                  // fraction of strings with a highlighted leader
uniform vec4 u_cycle;                  // glyph period, sequential, sync fraction, 0
uniform float u_ptime;                 // pulse clock (on the rain clock)
uniform float u_rain_time;             // elapsed time warped by the live speed factor
uniform float u_live_density;          // live density factor (1 = all rain)
uniform int u_msg_on;                  // rain message active this frame
uniform vec2 u_msg_t;                  // reveal_start, hide_start
uniform int u_msg_n;                   // message cycle index (jitter seed)
uniform int u_msg_lay[%(MAX_MON)d];    // main layer index per monitor
uniform vec4 u_msg_box[%(MAX_MON)d];   // col0, row0, cols, rows (cols 0: no message)
uniform float u_msg_off[%(MAX_MON)d];  // first row of the monitor's mask in u_msg
// the message's own finer glyph grid (message sizes below the reference): col0, row0, cols, rows (cols 0: none)
// of the mask in u_msg, and the cell size in px. The main grid carries no message then.
uniform vec4 u_msg_fbox[%(MAX_MON)d];
uniform vec2 u_msg_fcell[%(MAX_MON)d];
// stacked masks, R8 (texture unit 3)
uniform sampler2D u_msg;
// 1: letter cells latch on their own lane's heads (film presets, travel down)
uniform int u_msg_new;
uniform vec2 u_msg_rt;                 // rain-clock time of the reveal and of the deletion
// always-up clock: rain-clock time of the last minute change (-1: none), glitch seconds
uniform vec2 u_msg_ch;
uniform int u_img_grid;                // 1: the picture is drawn inside the main rain layer's own cells
uniform float u_img_gdepth;           // grid mode: 1 draws the picture in three depth classes, 0 at one cell size
uniform vec2 u_img_gs0;                // cell size share (x, y) of the near, mid and far classes
uniform vec2 u_img_gs1;
uniform vec2 u_img_gs2;
uniform float u_img_wdir;              // grid mode: 1 makes the code streams on side walls run along the perspective lines
uniform vec2 u_img_gscale;            // grid mode: picture cell size as a share of the rain cell (1: the rain's own cells)
uniform float u_img_gridge;            // grid mode: thin-line accent gain (second difference across the cell, per axis)
uniform float u_img_gedge;             // grid mode: edge accent share (cells are coarse, edges are everywhere)
uniform float u_img_ggamma;            // grid mode: tone contrast of the picture cells
uniform float u_img_gfloor;            // grid mode: rain trail brightness left in revealed cells
uniform float u_img_rain;              // rain brightness left where the image is revealed
uniform float u_img_fill;              // base glyph level on surfaces without edges
// share of the surface fill that does not follow tone (lower = more tonal contrast)
uniform float u_img_tone;
uniform float u_img_move;              // 0 still .. 1 full movement of the image glyphs
// image detail: thinnest glyph of the octave and box grids (px, 5 at detail 0); y is unused
uniform vec2 u_img_detail;
// image glyph cell as a fraction of the main cell: near, mid, far octave
uniform vec3 u_img_oct;
uniform float u_img_depthbias;         // shifts the fake depth (positive: more near glyphs)
uniform float u_img_orient;            // glyph rotation to the local edge direction (0 upright)
// glyphs settle from big/tilted: rows the head takes to pass (0: off), extra near-depth at the head
uniform vec2 u_img_settle;
// estimated vanishing points of the two images (0..1 image coords) and confidence 0..1
uniform vec3 u_img_vp0;
uniform vec3 u_img_vp1;
// perspective box grid: on (0 off), reference distance (fraction of width), glyph height there (rain cells)
uniform vec3 u_img_persp;
uniform float u_img_gback;
uniform vec4 u_img_gcoarse;            // grid mode: coarse tone dimming on far parts (0 none .. 1 far is dark), share, depth layering, silhouette gain
uniform float u_img_gcgamma;           // grid mode: coarse tone curve
uniform float u_img_gdpow;             // grid mode: inner detail curve (higher: only strong edges)
uniform vec4 u_img_gdet;               // grid mode: inner detail share, its level on far parts (0 dark .. 1 as near), column segment length in cells, near-side outlines (0 both sides .. 1)
uniform float u_img_gfw;
uniform float u_img_glane;
uniform float u_img_gstr;
uniform float u_img_gglow;
uniform vec2 u_img_gedgep;   // outline pass: cell scale (share of the mid class, 0 off), least outline strength
uniform vec3 u_img_gwhite;   // white heads over the picture: share of lanes whose heads light white in the picture passes, how white they are, how white the main rain's heads stay
uniform vec3 u_img_grain;    // rain through the subject: level of the string on the rain mask (label alpha), its trail curve, share of lanes
uniform float u_img_gedgecap;  // outline pass: at most this much brighter than the brightest side it divides (>= 1: no cap)
uniform float u_img_gpar;              // grid mode: parallax, near parts of the picture fall faster than far ones
uniform float u_img_gsgam;             // grid mode: string envelope gamma (higher: short bright head, long dark tail)
uniform float u_img_gboost;
uniform vec2 u_img_gpart;
// brightness a letter cell holds once the first stream has landed on it
uniform float u_msg_hold;
// image layer: 0 off, 1 one image up, 2 new image sweeping in over the old
uniform int u_img_on;
uniform int u_img_par;                 // texture channel (0: B, 1: A) of the current image
uniform sampler2D u_img0;              // images: R luminance, G open background (units 6 and 7)
uniform sampler2D u_img1;
// depth field of each image (units 8 and 9): R row coordinate V, G column coordinate U (rows of constant V), B glyph size (rain cells)
uniform sampler2D u_surf0;             // surface labels of the pictures (surfaces.py): value = kind * 50, 255 none
uniform sampler2D u_surf1;
uniform sampler2D u_imgf0;
uniform sampler2D u_imgf1;
uniform float u_img_hold;              // grid_hold: 1 the picture keeps in step with the rain's lanes (see image_reveal_cell)
// V range of the U table (min, max), mode (-1 octave grids, 0 flat, 1 depth field, 2 box grid), smallest glyph size in the field (rain cells)
uniform vec4 u_img_fv0;
uniform vec4 u_img_fv1;
// dim fill on near surfaces of the depth field (big glyphs on dark water or ground): amount, glyph size where it starts and is full (rain cells)
uniform vec3 u_img_nfill;
uniform vec2 u_img_size0;
uniform vec2 u_img_size1;
uniform vec3 u_img_lv;                 // glyph level from the image: black point, gain, edge gain
uniform float u_img_dim;               // rain level left in the darkest parts of the picture
// surface coat: level at full tone (0: off, edge-led level of img_level instead), share of it on the darkest surface, edge accent gain
uniform vec3 u_img_surf;
// surface coat: in sky and water only accents above x show, in full from y; z scales water accents
uniform vec3 u_img_sopen;
// surface coat: share of cells lit on the darkest and the brightest surface
uniform vec2 u_img_sdens;
// rain-clock time the current image is taken away again (-1: still up)
uniform float u_img_end;
// gap mode: rain-clock time the previous image was taken away (-1: none), so its exit runs on
// after the current image starts
uniform float u_img_pend;
// rain-clock start of the current image and of the previous one (which ends where the current starts)
uniform vec2 u_img_rt;
uniform int u_rip_lay;                 // main layer (the one that carries the rain)
uniform float u_gamma;                 // film tooth gamma (1: off)
uniform float u_exit_hold;             // grid exit: trail gamma of the strings that replace the picture (0: off)
uniform float u_lanes;                 // film lane density factor (1: off)
uniform vec2 u_clus;                   // cluster lattice lanes (whole), amplitude (0: off)
uniform int u_gslot;                   // changing-glyph slot, from looks.glyph_phase
uniform int u_gprev;                   // previous slot, for the crossfade frame
uniform float u_gmix;                  // crossfade weight of the previous glyph (0: off)
uniform float u_defocus;               // minimum glyph blur in cell widths (0: off)
// per-run layout value (0: the fixed layout used by the checks)
uniform uint u_run;
uniform float u_slices;                // 1 when this monitor draws the depth slices (screen blend)
uniform float u_pjit;                  // per-lane depth jitter amount (0: off)
// Reveal cache: the reveal of every main-layer cell (image_reveal_cell) is worked out once a frame
// in a small pre-pass (u_rev_pass 1) and read back from u_rev by image_reveal_a: rv, age, head + 2 byhead + 4 exit.
// Monitor mi's cells are rows mi * u_rev_rh .. of the cache.
uniform int u_rev_pass;
// The scene is compiled twice: STAGE 1 draws the rain layers, the grid particles and the classic
// picture glyphs (and fills the reveal cache); STAGE 2 draws only the grid picture passes, screen
// blended over it (GLRenderer._picture_pass). Apart the rain keeps the plain rain's register count:
// in one program the picture passes' code slowed every rain layer down with it.
const int STAGE = %(STAGE)d;
uniform int u_rev_rh;
uniform sampler2D u_rev;
out vec4 o_col;
%(COMMON)s

float wobble(float x) {
    return x + 0.3 * sin(1.41421356 * x) + 0.2 * sin(2.23606798 * x);
}

uint pcg(uint v) {
    uint s = v * 747796405u + 2891336453u;
    uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
    return (w >> 22u) ^ w;
}
float h1(uint a, uint b, uint c) {
    return float(pcg(a ^ pcg(b ^ pcg(c)))) * (1.0 / 4294967296.0);
}

// Per-lane speed drift at a given rain-clock time (0 when the layout is fixed).
float lane_drift(float rt, uint laneu, uint seed) {
    if (u_run == 0u) return 0.0;
    float dw = mix(0.15, 0.5, h1(laneu, seed, 12u)), dp = 6.2831853 * h1(laneu, seed, 13u);
    return 6.0 * sin(rt * dw + dp);
}
// grid exit hold window (u_exit_hold > 0): is tooth k one of the strings on this lane while the picture
// leaves (from the first to enter the top row after the end until the one on the cell 5 to 9 s later)?
// Strings already partway down at the end are not in it: the exit starts at the top.
bool exit_window_at(float en, float k, float o, float speed, float a, float T, uint laneu, uint seed) {
    if (en < 0.0) return false;
    // per-lane window, 5 to 9 s (the picture is gone after about 4.5 s with every string kept), so the
    // lanes go back to their own density at different times rather than all at once
    float te = en + 5.0 + 4.0 * h1(laneu, seed, 14u);
    float ks = floor(wobble(((en + o) * speed + lane_drift(en, laneu, seed)) / T)) + 1.0;
    float kz = floor(wobble(((te + o) * speed + lane_drift(te, laneu, seed) - a) / T));
    return k >= ks && k <= kz;
}
// (the current picture's exit, and the previous one's while it is still leaving)
bool exit_window(float k, float o, float speed, float a, float T, uint laneu, uint seed) {
    if (u_exit_hold <= 0.0 || u_img_hold <= 0.0 || u_img_grid != 1 || u_img_on == 0)
        return false;
    return exit_window_at(u_img_end, k, o, speed, a, T, laneu, seed)
        || (u_img_on == 2 && exit_window_at(u_img_pend, k, o, speed, a, T, laneu, seed));
}

// Structure of the picture around the cell centred at c (monitor px), read at the cell's mip
// level. Returns the detail (the stronger of edge and surface texture) and sets s to the
// texel (luminance, bright open background, surface tone, dark open background) and body to
// the broad light and shade.
float img_detail(sampler2D tex, vec2 isize, vec2 c, vec2 cell, vec2 ms, out vec4 s, out float body) {
    float lod = log2(max(1.0, cell.y * isize.y / ms.y));
    vec2 st = c / ms, dx = vec2(cell.x / ms.x, 0.0), dy = vec2(0.0, cell.y / ms.y);
    vec2 ic = img_cover(st, isize, ms);
    s = textureLod(tex, ic, lod);
    float l = s.r;
    float lx0 = textureLod(tex, img_cover(st - dx, isize, ms), lod).r, lx1 = textureLod(tex, img_cover(st + dx, isize, ms), lod).r;
    float ly0 = textureLod(tex, img_cover(st - dy, isize, ms), lod).r, ly1 = textureLod(tex, img_cover(st + dy, isize, ms), lod).r;
    float e = abs(lx1 - lx0) + abs(ly1 - ly0);
    // thin lines: a cell brighter or darker than both neighbours across it (the cell's own width
    // and height, so on a wall column or a floor row the neighbours are the next column or row)
    float ridge = u_img_grid == 1 ? max(abs(2.0 * l - lx0 - lx1), abs(2.0 * l - ly0 - ly1)) : 0.0;
    // texture: how far the cell departs from its wider surroundings (window grids, brick, road marks)
    float t = abs(textureLod(tex, ic, max(lod - 1.5, 0.0)).r - textureLod(tex, ic, lod + 1.5).r);
    // local contrast: dark facades and cars count as much as bright ones
    float rel = 1.0 / (l * 0.9 + 0.12);
    float edge = clamp(max(e, ridge * u_img_gridge) * rel * u_img_lv.z, 0.0, 1.0);   // vertices, outlines and thin lines: bright
    float tex_ = clamp(t * rel * u_img_lv.z * 1.5, 0.0, 1.0);    // surface texture: medium
    body = clamp((l - u_img_lv.x) * u_img_lv.y, 0.0, 1.0);       // broad light and shade: dim
    return max(edge, tex_ * 0.8);
}

// Glyph level the picture asks of a cell (edge-led look, used when u_img_surf.x is 0):
// outlines bright, surface texture medium, a base fill that follows tone, and no glyphs on
// smooth areas such as sky.
float img_level(sampler2D tex, vec2 isize, vec2 c, vec2 cell, vec2 ms) {
    vec4 s;
    float body;
    float detail = img_detail(tex, isize, c, cell, ms, s, body);
    // walls, figures and other surfaces: a base fill that follows tone, none on open background
    float fill = u_img_fill * smoothstep(0.0, 0.015, s.r) * (1.0 - s.g);
    return clamp(max(detail * 0.9 + body * 0.6 * smoothstep(0.08, 0.45, detail),
                     fill * (u_img_tone + (1.0 - u_img_tone) * min(s.r / 0.55, 1.0))), 0.0, 1.0);
}

// Surface coat (u_img_surf.x > 0), as in the film's corridor: every surface that is not open
// background carries glyphs whose level and share of lit cells follow its tone (texture B,
// worked out per picture with a local normalisation); edges and texture are a brighter
// accent on top.
// Returns (surface level, accent level, share of cells lit).
vec3 img_surface(sampler2D tex, vec2 isize, vec2 c, vec2 cell, vec2 ms) {
    vec4 s;
    float body;
    float detail = img_detail(tex, isize, c, cell, ms, s, body);
    float acc = pow(smoothstep(u_img_dim, 0.9, detail * 0.9 + body * 0.6 * smoothstep(0.08, 0.45, detail)), 1.4) * u_img_surf.z;
    float on = 1.0 - smoothstep(0.3, 0.7, max(s.g, s.a));
    // A: 1 sky, 0.75 water
    float wat = smoothstep(0.3, 0.6, s.a) * (1.0 - smoothstep(0.82, 0.95, s.a));
    // sky and water: only strong edges, water dimmer still
    acc *= mix(1.0, smoothstep(u_img_sopen.x, u_img_sopen.y, acc), smoothstep(0.3, 0.6, s.a)) * mix(1.0, u_img_sopen.z, wat);
    float tone = s.b;
    return vec3(u_img_surf.x * (u_img_surf.y + (1.0 - u_img_surf.y) * tone) * on, min(acc, 1.0),
                mix(u_img_sdens.x, u_img_sdens.y, tone) * on);
}

// Film lane density of lane `lane` on layer L (lane density factor and clustered lanes).
float lane_dens(int L, float lane, uint seed, float rows, float cols) {
    float dens = u_lay0[L].w;
    if (u_lanes != 1.0) dens = min(1.0, dens * u_lanes);
    if (u_clus.y > 0.0) {   // clustered lanes: smooth value noise over the lane index
        float cP = u_clus.x;
        float xc = lane / cP;
        float i0 = floor(xc), fr = xc - i0;
        float sfr = fr * fr * (3.0 - 2.0 * fr);
        if (u_run != 0u) {
            // the cluster field drifts, one new field every 40 s, cross-faded
            float te = u_time / 40.0 + h1(0u, seed, 15u) * 8.0;
            uint ep = uint(floor(te));
            float ef = fract(te); ef = ef * ef * (3.0 - 2.0 * ef);
            float na = mix(h1(uint(i0), seed + ep * 2u, 9u), h1(uint(i0 + 1.0), seed + ep * 2u, 9u), sfr);
            float nb = mix(h1(uint(i0), seed + ep * 2u + 2u, 9u), h1(uint(i0 + 1.0), seed + ep * 2u + 2u, 9u), sfr);
            float g = 1.0 + u_clus.y * (2.0 * mix(na, nb, ef) - 1.0);
            dens = clamp(dens * g, 0.0, 1.0);
        } else {
        float g = 1.0 + u_clus.y * (2.0 * mix(h1(uint(i0), seed, 9u), h1(uint(i0 + 1.0), seed, 9u), sfr) - 1.0);
        // divide by the exact mean gain over this monitor's lanes 0 .. nl - 1
        float nl = (u_dirmode == 1) ? rows : ((u_dirmode == 2) ? cols + rows : cols);
        int ip = int(cP);
        float sp = 0.0;
        for (int j = 0; j < ip; j++) { float t = float(j) / cP; sp += t * t * (3.0 - 2.0 * t); }
        int nint = int(ceil(nl / cP));
        float ni = h1(0u, seed, 9u), msum = 0.0;
        for (int i = 0; i < nint; i++) {
            float nn = h1(uint(i + 1), seed, 9u);
            float m = min(cP, nl - float(i) * cP);
            float sm = sp;
            if (m < cP) {
                sm = 0.0;
                for (int j = 0; j < int(m); j++) { float t = float(j) / cP; sm += t * t * (3.0 - 2.0 * t); }
            }
            msum += m * ni + (nn - ni) * sm;
            ni = nn;
        }
        g /= 1.0 + u_clus.y * (2.0 * msum / nl - 1.0);
        dens = clamp(dens * g, 0.0, 1.0);
        }
    }
    return dens;
}

bool g_rev_head = false;   // the head flag of the last image_reveal_cell call
bool g_rev_byhead = false; // grid_hold: the last cell took the current picture from a head (not the backstop)
bool g_rev_exit = false;   // grid_hold exit: the last cell is due to clear and still holds the picture
// grid_hold entry: the main cell under this pixel (set once in main() for the picture passes): its reveal,
// rows its bringing head has moved on, and whether a head brought it
vec2 g_mig_rv = vec2(0.0);
float g_mig_age = 0.0;
bool g_mig_by = false;

// Image layer: per rain cell of the main layer, has the first head after an image's
// start landed on it (and not yet the first head after its end)? One flag per channel.
// Uses the lane parameters of the film sawtooth, so the reveal follows the rain.
// One picture's state on main cell (lane, a), for the picture that started at st and is taken away at
// en (-1: not yet): 1 while the cell holds it. krv: the tooth that brought it; byhead: a head brought
// it (grid_hold, not the backstop); exiting: grid_hold, due to clear but still holding it.
float rev_state(float st, float en, float lane, float a, float rows, float cols, int L, uint seed,
                float o, float speed, float T, float xn, float kn, float dl, float fspeed,
                out float krv, out bool byhead, out bool exiting) {
    uint laneu = uint(lane);
    byhead = false;
    exiting = false;
    float kc = floor(wobble(((st + o) * speed + lane_drift(st, laneu, seed)) / T)) + 1.0;
    float fr0 = (u_rain_time - st - dl) * fspeed;   // rows the front has covered
    float cur = (kn >= kc || a <= fr0) ? 1.0 : 0.0;
    krv = kc;   // the tooth that brought the picture to this cell
    // a lane whose head or string is slow to come: after a backstop a head already on the screen
    // (it has passed the top row) is waited for however slow its lane, so a string never vanishes
    // with the rest of its lane changing in one frame; a lane with none changes from a front that
    // sweeps down from the top at the front's speed
    float dens = lane_dens(L, lane, seed, rows, cols);
    bool lit = u_run != 0u || h1(laneu, seed, 7u) < dens;   // a fixed layout's unlit lane has no heads
    if (u_img_hold > 0.0) {
        // grid_hold: the rain brings the picture. A cell takes it when the first lit head reaches it after
        // the start (a string already on the cell then does not count, or bands would appear at once,
        // with no head); no front, so nothing is laid down where no string has passed.
        float ks = floor(wobble(((st + o) * speed + lane_drift(st, laneu, seed) - a) / T));
        cur = 0.0;
        krv = kn;
        float jf = 0.0;
        bool found = false;
        if (lit) {
            for (int i = 1; i <= 16; i++) {
                float j = ks + float(i);
                uint ju = uint(j + 65536.0);
                if (u_run != 0u && h1(laneu, seed + 900u, ju) >= dens) continue;   // dropped by churn
                if (u_live_density - h1(laneu, seed + 800u, ju) <= -0.05) continue;  // not shown
                jf = j;
                found = true;
                break;
            }
        }
        float tbk = st + 6.0 + 3.0 * h1(laneu, seed, 10u);
        bool wait = found && jf <= floor(wobble(((tbk + o) * speed + lane_drift(tbk, laneu, seed)) / T));
        float tsw = tbk + a / fspeed;   // the backstop front reaches this cell
        if (found && kn >= jf) {
            cur = 1.0;
            krv = jf;
            byhead = true;
        }
        if (!wait && u_rain_time >= tsw) cur = 1.0;   // backstop
        // a head that comes after the backstop front finds the picture already there
        if (byhead && !wait && u_rain_time - (xn - krv) * T / max(speed, 1e-3) > tsw) byhead = false;
    }
    // gap mode: the first head to enter the top row after the end takes the picture away, top to bottom.
    // Only a real head does it (a lane cleared without one would go black).
    if (en >= 0.0) {
        float ke = floor(wobble(((en + o) * speed + lane_drift(en, laneu, seed)) / T)) + 1.0;
        if (u_img_hold > 0.0) {
            // grid_hold: the rain takes the picture away, from the top. A cell falls due when the first
            // head to enter the top row after the end reaches it (strings already partway down at the end
            // do not count, or their trails came up all over the screen at once); it keeps the picture
            // until a lit string of its main lane covers it; cells in the gaps between strings keep
            // it, so the picture is replaced glyph by glyph and no gap shows black beside it.
            // A lane whose head never comes is cleared by the backstop front 6 to 9 s after the end.
            float tbe = en + 6.0 + 3.0 * h1(laneu, seed, 9u);
            bool bdue = u_rain_time >= tbe + a / fspeed;   // the backstop front has reached this cell
            if (cur > 0.0 && (kn >= ke || bdue)) {
                float kd = ke;
                // the string must be bright where it covers the cell: its head and the upper half of its
                // lit trail (base above half the head's level), not the faint end of the trail, which read
                // as a dark line through the picture (u_saw: base = b * contrast + bias, b = 1 - fract(w))
                // (half the shown level: base^gamma >= 0.5 top^gamma)
                float top = min(u_saw.y + u_saw.z, 1.0);
                float half_ = top * pow(0.5, 1.0 / max(u_gamma, 0.1));
                float thr = u_saw.y > 0.0 ? clamp(1.0 - (half_ - u_saw.z) / u_saw.y, 0.0, 1.0) : 1.0;
                float jf = 0.0;
                bool found = false;
                if (lit) {
                    for (int i = 0; i < 16; i++) {
                        float j = kd + float(i);
                        uint ju = uint(j + 65536.0);
                        bool xkeep = u_exit_hold > 0.0 && u_img_grid == 1 && exit_window_at(en, j, o, speed, a, T, laneu, seed);   // exit hold keeps every string
                        if (u_run != 0u && !xkeep && h1(laneu, seed + 900u, ju) >= dens) continue;   // dropped by churn
                        if (u_live_density - h1(laneu, seed + 800u, ju) <= -0.05) continue;  // not shown
                        jf = j;
                        found = true;
                        break;
                    }
                }
                // the string takes the picture only once its bright part has passed: under its head and
                // upper trail the picture still shows, so the falling glyphs lie over the picture instead
                // of each carrying a black strip of cleared cells the width of its lane
                bool gone = found && (kn > jf || (kn == jf && fract(xn) >= thr));
                bool wait = found && jf <= floor(wobble(((tbe + o) * speed + lane_drift(tbe, laneu, seed)) / T));
                if (!wait && bdue) gone = true;   // backstop front
                if (gone) cur = 0.0;
                exiting = cur > 0.0;
            }
        } else {
            bool late = u_rain_time - en > 2.5 + 2.0 * h1(laneu, seed, 9u);
            if (kn >= ke || late) cur = 0.0;
        }
    }
    return cur;
}
vec2 image_reveal_cell(vec2 cr, float rows, float cols, int mi, out float age, out bool head) {
    int L = u_rip_lay;
    uint seed = uint(L * 64 + mi * 8 + 1);
    if (u_run != 0u) seed = pcg(seed ^ pcg(u_run));
    uint laneu = uint(cr.x);
    float a = cr.y;
    float speed = mix(u_speed.x, u_speed.y, h1(laneu, seed, 1u)) * u_lay0[L].z;
    float T = u_saw.x * u_lay1[L].x;
    float o = h1(laneu, seed, 4u) * 1000.0;
    float dfr = (u_run != 0u) ? lane_drift(u_rain_time, laneu, seed) : 0.0;
    float xn = wobble(((u_rain_time + o) * speed + dfr - a) / T);
    float kn = floor(xn);
    // First head to enter at the top row, so the picture sweeps down from the top. A lane whose
    // head is slow to come would sit in plain rain for many seconds beside lanes already
    // revealed, so after a short per-lane delay a front travels down at the lane's own speed and
    // reveals it anyway (whichever of the head and the front gets to a cell first).
    const float FRONT_DELAY = 0.6;
    float dl = h1(laneu, seed, 7u) * FRONT_DELAY;
    // the front rushes down the lane in two to three seconds whatever the lane's rain speed
    float fspeed = rows / (1.0 + 0.8 * h1(laneu, seed, 8u));
    float krv;
    bool byh, xit;
    float cur = rev_state(u_img_rt.x, u_img_end, cr.x, a, rows, cols, L, seed, o, speed, T, xn, kn, dl, fspeed, krv, byh, xit);
    g_rev_byhead = byh;
    g_rev_exit = xit;
    head = cur > 0.0 && kn == krv;   // the head that brought the picture is on this cell's tooth
    g_rev_head = head;
    // the string that brought the picture (or a lane the front revealed before its head came)
    // keeps its trail at full rain: cutting it left dark lanes beside lanes still in plain rain
    // (its envelope: full at its head, down to the picture level where the next head comes)
    // (no hold on the way in: the rain kept over the forming picture read as straight rain through it)
    // rows the head or the front has moved on past this cell (the current image)
    float fr0 = (u_rain_time - u_img_rt.x - dl) * fspeed;
    age = cur > 0.0 ? (u_img_hold > 0.0 ? max(0.0, xn - krv) * T : max(max(0.0, xn - krv) * T, max(0.0, fr0 - a))) : 0.0;
    float prv = 0.0;
    if (u_img_on == 2) {
        if (u_img_pend >= 0.0) {
            // gap mode: the previous picture's exit runs on where the current one has not arrived yet
            // (dropping it at the start changed every lane still holding it in one frame)
            float k2;
            bool b2, x2;
            prv = cur > 0.0 ? 0.0 : rev_state(u_img_rt.y, u_img_pend, cr.x, a, rows, cols, L, seed, o, speed, T, xn, kn, dl, fspeed, k2, b2, x2);
            if (prv > 0.0) g_rev_exit = x2;
        } else {
            float k0 = floor(wobble(((u_img_rt.y + o) * speed + lane_drift(u_img_rt.y, laneu, seed)) / T)) + 1.0;
            // the previous image ends where the current one starts
            prv = ((kn >= k0 || a <= (u_rain_time - u_img_rt.y - dl) * fspeed) && cur == 0.0) ? 1.0 : 0.0;
        }
    }
    return u_img_par == 0 ? vec2(cur, prv) : vec2(prv, cur);
}
// The main layer's grid on a monitor: cell (px), columns, rows and left pad.
void rev_grid(vec2 ms, float dpi, out vec2 cell, out float cols, out float rows, out float padx) {
    int L = u_rip_lay;
    float sc = u_lay0[L].x * dpi * u_gscale;
    cell = floor(vec2(%(CELL_W)f, %(CELL_H)f) * sc + 0.5);
    if (u_cols > 0.0) cell = vec2(max(4.0, floor(ms.x / u_cols * u_lay0[L].x * u_gscale + 0.5)));
    cols = floor(ms.x / cell.x);
    rows = floor(ms.y / cell.y);
    padx = floor((ms.x - cols * cell.x) * 0.5);
}
// image_reveal_cell of main cell cr, read from the reveal cache (sets g_rev_head, g_rev_byhead and g_rev_exit too)
vec2 rev_fetch(vec2 cr, int mi, out float age, out bool head) {
    vec4 v = texelFetch(u_rev, ivec2(int(cr.x), mi * u_rev_rh + int(cr.y)), 0);
    age = v.z;
    int f = int(v.w);
    head = (f & 1) != 0;
    g_rev_head = head;
    g_rev_byhead = (f & 2) != 0;
    g_rev_exit = (f & 4) != 0;
    return v.xy;
}
vec2 image_reveal_a(vec2 mp, vec2 ms, float dpi, int mi, out float age) {
    vec2 cell;
    float cols, rows, padx;
    rev_grid(ms, dpi, cell, cols, rows, padx);
    vec2 cr = clamp(floor((mp - vec2(padx, 0.0)) / cell), vec2(0.0), vec2(cols - 1.0, rows - 1.0));
    bool head;
    return rev_fetch(cr, mi, age, head);
}
vec2 image_reveal(vec2 mp, vec2 ms, float dpi, int mi) {
    float age;
    return image_reveal_a(mp, ms, dpi, mi, age);
}


// Surface kind of the picture at a monitor point (cc, px): 0 frontal, 1 left wall, 2 right wall,
// 3 floor, 4 ceiling; -1 when the picture has no detection. disp: the network's disparity there
// (0 far .. 1 near), -1 without detection.
int img_label(bool useA, vec2 cc, vec2 ms, out float disp, out float tone) {
    vec2 isz = useA ? u_img_size0 : u_img_size1;
    vec2 ic = img_cover(cc / ms, isz, ms);
    vec3 v = useA ? textureLod(u_surf0, ic, 0.0).rgb : textureLod(u_surf1, ic, 0.0).rgb;
    disp = v.x > 0.99 ? -1.0 : v.y;
    tone = v.x > 0.99 ? -1.0 : v.z;
    return v.x > 0.99 ? -1 : int(v.x * 255.0 / 50.0 + 0.5);
}
// Rain mask of the picture at a point (surfaces.rain_mask): 1 on the subject, fading below it.
float img_rain(bool useA, vec2 cc, vec2 ms) {
    vec2 isz = useA ? u_img_size0 : u_img_size1;
    vec2 ic = img_cover(cc / ms, isz, ms);
    vec4 v = useA ? textureLod(u_surf0, ic, 0.0) : textureLod(u_surf1, ic, 0.0);
    return v.x > 0.99 ? 0.0 : v.a;
}
int img_label(bool useA, vec2 cc, vec2 ms, out float disp) {
    float t;
    return img_label(useA, cc, ms, disp, t);
}
int img_label(bool useA, vec2 cc, vec2 ms) {
    float d;
    return img_label(useA, cc, ms, d);
}

// Depth class of the picture at a point (the fake depth of the classic path: far from the
// vanishing point is near the viewer, fine texture is far): 0 near, 1 mid, 2 far.
int img_depth_class(bool useA, vec2 cc, vec2 ms, vec2 cell0) {
    vec2 isz = useA ? u_img_size0 : u_img_size1;
    vec3 ivp = useA ? u_img_vp0 : u_img_vp1;
    vec2 ic0 = img_cover(cc / ms, isz, ms);
    float lodm = log2(max(1.0, cell0.y * u_img_oct.y * isz.y / ms.y));
    float rough = abs(useA ? textureLod(u_img0, ic0, lodm).r - textureLod(u_img0, ic0, lodm + 2.0).r
                           : textureLod(u_img1, ic0, lodm).r - textureLod(u_img1, ic0, lodm + 2.0).r);
    vec2 dv = (ic0 - ivp.xy) * vec2(isz.x / isz.y, 1.0);
    float near = smoothstep(0.15, 1.0, length(dv));
    float dep = clamp(0.8 * near + 0.2 * (1.0 - clamp(rough * 8.0, 0.0, 1.0)) + u_img_depthbias, 0.0, 1.0);
    // a detected picture has its own depth: the network's disparity, near (high) draws large cells
    float disp;
    img_label(useA, cc, ms, disp);
    if (disp >= 0.0) dep = clamp(disp + u_img_depthbias, 0.0, 1.0);
    return dep > 0.66 ? 0 : (dep > 0.36 ? 1 : 2);
}

// Perspective box grid, as in the film's corridor: with the vanishing point vpm (px), the
// screen splits into a left and a right wall, a floor (below the diagonals to the bottom
// corners) and, near the vanishing point, a flat back wall. On a wall the glyph rows run
// toward the vanishing point and the glyphs shrink with depth (height ~ D, width ~ D^2, D the
// distance from the vanishing point); on the floor the glyphs lie flat, foreshortened upward.
// cn: glyph cell (px) at distance R; back: back-wall cell (px); minpx: thinnest glyph allowed.
// Out: g (continuous grid coords, cell = one glyph), cc cell centre (px), csz cell size at the centre (px), reg.
// Camera looking up (vanishing point z > 1.5): every surface below the point streams radially out of
// it, rain coming from the sky at the camera. Set before each img_persp call.
bool g_radial = false;
// The detector's surface kind at the point being drawn (img_label; -1 none). A floor label below the
// vanishing point is drawn as floor, a wall label as wall, whichever side of the diagonals it lies on:
// a wide floor (a road, a hall) reaches past them, and a wall can reach below them. Set with g_radial.
int g_pkind = -1;

void img_persp(vec2 mp, vec2 ms, vec2 vpm, vec2 cn, vec2 back, float minpx, vec2 cw, vec2 cf, out vec2 g, out vec2 cc, out vec2 csz, out int reg) {
    float R = u_img_persp.y * ms.x;
    vec2 d = mp - vpm;
    float sx = d.x < 0.0 ? max(vpm.x, 1.0) : max(ms.x - vpm.x, 1.0);
    float sy = max(ms.y - vpm.y, 1.0);
    bool flr = d.y > 0.0 && (g_radial || d.y * sx > abs(d.x) * sy);
    if (!g_radial && d.y > 0.0) {
        if (g_pkind == 3) flr = true;
        else if (g_pkind == 1 || g_pkind == 2) flr = false;
    }
    // cw / cf: the wall / floor glyph size (px) at the screen edge, giving the cell at distance R that
    // reproduces it (zero: use cn as given). Rows of a floor shrink with D squared, columns of a wall too.
    if (cw.x > 0.0 && !flr) cn = vec2(cw.x * R * R / (sx * sx), cw.y * R / sx);
    if (cf.x > 0.0 && flr) cn = vec2(cf.x * R / sy, cf.y * R * R / (sy * sy));
    float D = flr ? d.y : abs(d.x);
    // nearer the vanishing point the glyphs would get thinner than minpx
    float Dmin = R * sqrt(minpx / (flr ? cn.y : cn.x));
    // looking up, the fan runs on into the sky strip (the rays converge there, so the cells get thin)
    if (g_radial) Dmin *= 0.35;
    float sg = d.x < 0.0 ? 1.0 : -1.0;
    if (D < Dmin) {
        reg = 0;
        g = d / back;
        cc = vpm + (floor(g) + 0.5) * back;
        csz = back;
        return;
    }
    vec2 gc;
    if (!flr) {
        reg = d.x < 0.0 ? 1 : 2;
        g = vec2(sg * R * R / (cn.x * D), d.y * R / (cn.y * D));
        gc = floor(g) + 0.5;
        float Dc = R * R / (cn.x * abs(gc.x));
        cc = vpm + vec2(-sg * Dc, gc.y * cn.y * Dc / R);
        csz = vec2(cn.x * Dc * Dc / (R * R), cn.y * Dc / R);
    } else {
        reg = 3;
        float cnx = cn.x;
        g = vec2(d.x * R / (cnx * D), -R * R / (cn.y * D));
        gc = floor(g) + 0.5;
        float Dc = R * R / (cn.y * abs(gc.y));
        cc = vpm + vec2(gc.x * cnx * Dc / R, Dc);
        csz = vec2(cnx * Dc / R, cn.y * Dc * Dc / (R * R));
    }
}

vec3 layer_color(int L, vec2 mp, vec2 ms, float dpi, int mi, vec2 csm, int dcl) {
    float sc = u_lay0[L].x * dpi * u_gscale;
    vec2 cell = floor(vec2(%(CELL_W)f, %(CELL_H)f) * sc + 0.5);
    if (u_cols > 0.0) cell = vec2(max(4.0, floor(ms.x / u_cols * u_lay0[L].x * u_gscale + 0.5)));
    vec2 cell0 = cell;
    // grid mode: the picture's own cells over the main layer's lanes, picture only (the depth passes
    // always, whatever their cell size: a near class at 1.0 or more drew nothing otherwise)
    bool fine = csm.y < 1.0 || dcl >= 0;
    if (fine) cell = max(vec2(3.0), floor(cell * csm + 0.5));
    // dcl -2: the perspective pass (pictures with a confident vanishing point): wall and floor
    // cells of the picture's perspective box, columns and rows of one grid that recedes.
    bool persp = fine && dcl == -2;
    vec2 mgr = vec2(1.0);          // grid_hold entry: the enlargement there (glyph sharpness)
    float mig = 1.0, menv = 1.0;   // grid_hold entry: how far the cell has settled (0 at the head, 1 settled), the bringing string's envelope
    // grid_hold, entry: the picture's cells come out of the main rain's straight lanes. Just behind the
    // head that brought the picture, the lane shows the picture enlarged to the main cell size (plain rain
    // glyphs in a straight lane, lit by that string); as the string falls on, it opens out into the
    // picture's own finer cells and perspective and settles on them (MIG_ROWS rows behind the head).
    if (fine && u_img_hold > 0.0 && u_img_grid == 1 && u_img_on != 0 && u_film == 1 && u_dirmode == 0 && L == u_rip_lay) {
        const float MIG_ROWS = 16.0;
        float cols0 = floor(ms.x / cell0.x), rows0 = floor(ms.y / cell0.y);
        float padx0 = floor((ms.x - cols0 * cell0.x) * 0.5);
        vec2 cr0 = clamp(floor((mp - vec2(padx0, 0.0)) / cell0), vec2(0.0), vec2(cols0 - 1.0, rows0 - 1.0));
        // the reveal of this main cell, read once per pixel in main()
        float age0 = g_mig_age;
        vec2 rv0 = g_mig_rv;
        // only where a head brought the current picture (a backstop lane's tooth count restarts every tooth)
        if (!g_mig_by || (u_img_par == 0 ? rv0.x : rv0.y) <= 0.0) rv0 = vec2(0.0);
        float ms0 = smoothstep(0.2 * MIG_ROWS, MIG_ROWS, age0);
        if (rv0.x + rv0.y > 0.0) {
            mig = ms0;
            // the envelope of the main lane's string that brought the picture (age0 rows behind its head)
            menv = pow(clamp(1.0 - age0 / (u_saw.x * u_lay1[L].x), 0.0, 1.0), u_img_gsgam);
        }
        if (rv0.x + rv0.y > 0.0 && ms0 < 1.0) {
            // the lane's centre and the head that brought the picture (px; the same all down the lane)
            float xc = padx0 + (cr0.x + 0.5) * cell0.x;
            float hy = (cr0.y + 0.5 + age0) * cell0.y;
            // the picture column under the lane's centre, and the picture cell's size as a share of the main cell
            float tcx = xc;
            vec2 tk = min(cell / cell0, vec2(1.0));
            if (persp) {
                bool uA0 = rv0.x > 0.0;
                vec3 ivp0 = uA0 ? u_img_vp0 : u_img_vp1;
                if (ivp0.z > 0.5 && u_img_persp.x > 0.0) {
                    g_radial = ivp0.z > 1.5;
                    g_pkind = img_label(uA0, vec2(xc, mp.y), ms);
                    vec2 vpm0 = img_uncover(ivp0.xy, uA0 ? u_img_size0 : u_img_size1, ms) * ms;
                    vec2 g0, tc0, csz0;
                    int rg0;
                    img_persp(vec2(xc, mp.y), ms, vpm0, cell0 * csm * u_img_persp.z / 0.7, max(floor(cell * 0.6 + 0.5), vec2(3.0)), 2.0, cell0 * vec2(0.4, 0.8), cell0 * vec2(0.4 * u_img_gfw, 0.9), g0, tc0, csz0, rg0);
                    tcx = tc0.x;
                    tk.x = min(csz0.x / cell0.x, 1.0);
                }
            } else {
                float colsf = floor(ms.x / cell.x), padf = floor((ms.x - colsf * cell.x) * 0.5);
                tcx = padf + (floor((xc - padf) / cell.x) + 0.5) * cell.x;
            }
            // across: the lane shows that one column enlarged to the lane's width, opening out to the
            // picture's columns; down: the picture behind the head is stretched toward the head and
            // falls back into place, its rows shrinking from the main row height to their own
            mgr = mix(tk, vec2(1.0), ms0);
            mp = vec2(mix(tcx + (mp.x - xc) * tk.x, mp.x, ms0), hy - (hy - mp.y) * mgr.y);
        }
    }
    float cols = floor(ms.x / cell.x);
    float rows = floor(ms.y / cell.y);
    float padx = floor((ms.x - cols * cell.x) * 0.5);
    vec2 q = vec2(mp.x - padx, mp.y);
    vec2 cr, f, pcc = vec2(0.0);
    bool pwall = false, pleft = false;
    if (persp) {
        float pa;
        vec2 rp0 = image_reveal_a(clamp(mp, vec2(0.0), ms - 1.0), ms, dpi, mi, pa);
        if (rp0.x + rp0.y == 0.0) return vec3(0.0);
        bool uA = rp0.x > 0.0;
        vec3 ivp = uA ? u_img_vp0 : u_img_vp1;
        if (ivp.z < 0.5 || u_img_persp.x <= 0.0) return vec3(0.0);
        g_radial = ivp.z > 1.5;
        g_pkind = img_label(uA, mp, ms);
        vec2 vpm = img_uncover(ivp.xy, uA ? u_img_size0 : u_img_size1, ms) * ms;
        vec2 g, csz;
        int preg_;
        img_persp(mp, ms, vpm, cell0 * csm * u_img_persp.z / 0.7, max(floor(cell * 0.6 + 0.5), vec2(3.0)), 2.0, cell0 * vec2(0.4, 0.8), cell0 * vec2(0.4 * u_img_gfw, 0.9), g, pcc, csz, preg_);
        if (pcc.x < 0.0 || pcc.y < 0.0 || pcc.x >= ms.x || pcc.y >= ms.y) return vec3(0.0);
        // a detected foreground object or far wall that faces the viewer is not a surface of the box
        if (img_label(uA, pcc, ms) == 0) return vec3(0.0);
        cr = floor(g);
        f = g - cr;
        pwall = preg_ == 1 || preg_ == 2;
        pleft = preg_ == 1;
        cr += vec2(4096.0 + 2048.0 * float(preg_), 128.0);   // rows run both ways from the vanishing point, keep them positive
        cell = csz;
        rows = 256.0;
    } else {
        if (q.x < 0.0 || q.x >= cols * cell.x || q.y >= rows * cell.y) return vec3(0.0);
        cr = floor(q / cell);
        f = q / cell - cr;
    }
    uint seed = uint(L * 64 + mi * 8 + 1);
    if (u_run != 0u) seed = pcg(seed ^ pcg(u_run));

    // Lane, position along the lane and lane length for the travel direction.
    float lane = cr.x, a = cr.y, extent = rows;
    if (u_dirmode == 1) { lane = cr.y; a = cr.x; extent = cols; }
    else if (u_dirmode == 2) { lane = cr.x - cr.y + rows; }
    // streams on walls run along the perspective lines, toward the viewer on both walls (the left wall's
    // depth coordinate grows toward the vanishing point, the right wall's toward the viewer)
    if (pwall && u_img_wdir > 0.5) { lane = cr.y; a = pleft ? -cr.x : cr.x; }
    uint laneu = uint(lane);
    uint cellu = uint(cr.x) * 4099u + uint(cr.y);

    // Picture in the rain's own grid (image_mode grid): the main layer's cell takes a glyph level
    // from the picture once the head latch of its lane has reached it (see image_reveal_cell).
    float plv = 0.0;
    float prm = 0.0;   // rain through the subject: the picture's rain mask at this cell (picture passes)
    bool pgrid = u_img_grid == 1 && u_img_on != 0 && u_film == 1 && u_dirmode == 0 && L == u_rip_lay;
    if (fine && !pgrid) return vec3(0.0);
    bool preg = false, phead = false, rdrop = false;
    bool pbring = false;   // the head that brings the picture to this cell (reveal)
    float pdn = -1.0;   // the picture's depth at this cell (0 far, 1 near), -1 without a depth map
    if (pgrid) {
        float page;
        bool ph;
        vec2 pcc0 = persp ? pcc : vec2(padx, 0.0) + (cr + 0.5) * cell;
        vec2 pr;
        if (fine && u_img_hold > 0.0) {
            // grid_hold: a picture cell takes the reveal of the main lane it sits on, so the picture
            // comes and goes with that lane's rain (on lanes of its own it could come later than the
            // main lane stepped back, or go sooner, and leave a dark lane between)
            pr = image_reveal_a(clamp(pcc0, vec2(0.0), ms - 1.0), ms, dpi, mi, page);
            ph = g_rev_head;
        } else if (!fine) {
            pr = rev_fetch(cr, mi, page, ph);   // the main layer's own cell: the cached reveal
        } else {
            pr = image_reveal_cell(cr, rows, cols, mi, page, ph);
        }
        pbring = ph;
        preg = pr.x + pr.y > 0.0;
        // with a finer picture grid the main layer's own cells carry no picture (only preg and the
        // bringing head count there), so the picture's tone is not worked out for them
        if (preg && (fine || u_img_gscale.y >= 1.0)) {
            bool useA = pr.x > 0.0;
            vec2 cc = pcc0;
            uint pseed = uint(L * 64 + mi * 8 + 5);
            if (fine && dcl >= 0 && dcl != 3) {
                // pictures with a confident vanishing point are drawn by the perspective pass
                // (frontal parts of a detected picture are the flat passes' own)
                if (u_img_persp.x > 0.0 && (useA ? u_img_vp0.z : u_img_vp1.z) > 0.5 && img_label(useA, cc, ms) != 0) return vec3(0.0);
                if (img_depth_class(useA, cc, ms, cell0) != dcl) return vec3(0.0);
            }
            uint cx = uint(cr.x), cy = uint(cr.y);
            if (u_img_surf.x > 0.0) {
                vec3 q = useA ? img_surface(u_img0, u_img_size0, cc, cell, ms) : img_surface(u_img1, u_img_size1, cc, cell, ms);
                // one glyph per cell, so tone is read as brightness (a share of lit cells would only add noise)
                plv = max(pow(clamp(q.x * q.z / max(u_img_surf.x * u_img_sdens.y, 1e-3), 0.0, 1.0), u_img_ggamma), u_img_gedge * q.y);
                float disp, ct;
                img_label(useA, cc, ms, disp, ct);
                if (u_img_gcoarse.y > 0.0 && ct >= 0.0) {
                    // coarse tone: raw light of the picture blurred over several cells (stretched per picture), so
                    // large light and shade reaches the screen; depth makes near brighter and far dimmer
                    // depth shades the tone (near bright, far dim) and its jumps draw object outlines
                    // one level per column segment: tone and depth read at the segment's middle row
                    vec2 cs = cc;
                    if (u_img_gdet.z > 1.0 && !persp) {
                        cs.y = (floor(cr.y / u_img_gdet.z) * u_img_gdet.z + 0.5 * u_img_gdet.z) * cell.y;
                        img_label(useA, cs, ms, disp, ct);
                        if (ct < 0.0) { cs = cc; img_label(useA, cc, ms, disp, ct); }
                    }
                    float dn = clamp(disp, 0.0, 1.0);
                    pdn = dn;
                    float sil = 0.0, side = ct;
                    if (u_img_gcoarse.w > 0.0) {
                        float d1, d2, d3, d4, t1, t2, t3, t4;
                        vec2 st = cell * 1.0;
                        img_label(useA, cs + vec2(st.x, 0.0), ms, d1, t1);
                        img_label(useA, cs - vec2(st.x, 0.0), ms, d2, t2);
                        img_label(useA, cs + vec2(0.0, st.y), ms, d3, t3);
                        img_label(useA, cs - vec2(0.0, st.y), ms, d4, t4);
                        side = max(max(ct, max(t1, t2)), max(t3, t4));
                        // both sides of a depth jump, or only the nearer side (the object, not a ring round it)
                        float both = abs(d1 - d2) + abs(d3 - d4);
                        float nside = 2.0 * max(0.0, dn - min(min(d1, d2), min(d3, d4)));
                        sil = clamp(mix(both, nside, u_img_gdet.w) * u_img_gcoarse.w * 4.0, 0.0, 1.0);
                    }
                    // far parts lose their light (a lit wall behind a near object stays behind it)
                    ct *= 1.0 - u_img_gcoarse.x * (1.0 - dn);
                    float base = pow(clamp(mix(ct, dn, u_img_gcoarse.z), 0.0, 1.0), u_img_gcgamma);
                    // outlines in finer glyphs (dcl 3, the outline pass): that pass draws the outline alone and
                    // the other passes leave it out
                    if (dcl == 3) {
                        if (sil < u_img_gedgep.y) return vec3(0.0);
                        // never brighter than the parts it divides by more than the cap: a person's outline
                        // must not outshine their face
                        plv = min(sil * 0.9, pow(clamp(side, 0.0, 1.0), u_img_gcgamma) + u_img_gedgecap);
                        base = -1.0;
                    } else if (u_img_gedgep.x <= 0.0) base = max(base, sil * 0.9);
                    // inner detail (windows, signs, chairs): the cell's own edge and texture accent, dimmer on far parts
                    float farf = mix(u_img_gdet.y, 1.0, dn);
                    float det = pow(q.y, u_img_gdpow) * farf;
                    // the cell's own tone (kept when grid_coarse < 1) is dimmed on far parts as well
                    if (base >= 0.0) plv = min(1.0, max(mix(plv * farf, base, u_img_gcoarse.y), u_img_gedge * det) + u_img_gdet.x * det);
                } else if (dcl == 3) return vec3(0.0);
            } else {
                float lv = useA ? img_level(u_img0, u_img_size0, cc, cell, ms) : img_level(u_img1, u_img_size1, cc, cell, ms);
                plv = pow(smoothstep(u_img_dim, 0.9, lv), 1.4);
            }
            phead = ph && plv > 0.3 && (u_img_par == 0 ? pr.x : pr.y) > 0.0;
            if (fine && dcl != 3 && u_img_grain.x > 0.0) prm = img_rain(useA, cc, ms) * u_img_grain.x;
        }
    }
    if (fine && plv <= 0.0 && prm <= 0.0) return vec3(0.0);

    // Rain message: 0 none, 1 lit, 2 leader. The front steps whole cells.
    int msg = 0;
    bool mcell = false;   // a letter cell of the head-latched message
    int mkind = 0;        // always-up clock, minute change: 0 stays, 1 appears, 2 vanishes
    if (u_msg_on == 1 && u_msg_new == 1 && u_film == 1 && u_dirmode == 0 && L == u_msg_lay[mi] && !fine) {
        // The rain is left exactly as it is. A letter cell lights when the first head
        // of its own lane lands on it after the reveal and stays lit until the first
        // head after the deletion time (see the saw model below).
        vec4 box = u_msg_box[mi];
        if (box.z > 0.0 && cr.x >= box.x && cr.x < box.x + box.z
                        && cr.y >= box.y && cr.y < box.y + box.w)
        {
            float mv = texelFetch(u_msg, ivec2(int(cr.x - box.x), int(u_msg_off[mi] + cr.y - box.y)), 0).r;
            // 1.0 stays, 0.75 appears, 0.38 vanishes (change codes, rain_message.change_codes)
            mcell = mv > 0.25;
            mkind = mv > 0.9 ? 0 : (mv > 0.5 ? 1 : 2);
        }
    } else if (u_msg_on == 1 && L == u_msg_lay[mi] && !fine) {
        vec4 box = u_msg_box[mi];
        if (box.z > 0.0 && cr.x >= box.x && cr.x < box.x + box.z
                        && cr.y >= box.y && cr.y < box.y + box.w) {
            float mv = texelFetch(u_msg, ivec2(int(cr.x - box.x),
                                               int(u_msg_off[mi] + cr.y - box.y)), 0).r;
            if (mv > 0.5) {
                float a0 = (u_dirmode == 1) ? box.x : box.y;
                float j1 = h1(laneu, uint(mi) * 16u + 900u, uint(u_msg_n));
                float j2 = h1(laneu, uint(mi) * 16u + 901u, uint(u_msg_n));
                float fr = floor(a0 - 4.0 * j1 + (u_time - u_msg_t.x - 0.6 * j2) * 30.0);
                float de = floor(a0 - 4.0 * j1 + (u_time - u_msg_t.y - 0.6 * j2) * 30.0);
                if (fr >= a && de < a) msg = (fr == a) ? 2 : 1;
            }
        }
    }

    // Per-lane depth jitter on every slice but the main one (dim and speed).
    float ldim = u_lay0[L].y;
    float pj = 1.0;
    if (u_slices > 0.5 && L != u_msg_lay[mi]) {
        pj = 1.0 + u_pjit * (h1(laneu, seed, 11u) - 0.5);
        ldim /= pj;
    }
    float speed = mix(u_speed.x, u_speed.y, h1(laneu, seed, 1u)) * u_lay0[L].z;
    if (u_slices > 0.5) speed /= pj;
    // picture passes count rows in their own (smaller) cells: same pixel speed as the rain around them
    if (fine) speed /= csm.y;
    // parallax on the flat depth passes: near parts fall faster than the wall behind them
    if (fine && dcl >= 0 && pdn >= 0.0) speed *= max(0.2, 1.0 + u_img_gpar * (pdn - 0.5));
    float col_r = 0.0, col_g = 0.0;      // film: brightness, leader flag
    float br = 0.0, headness = 0.0, dist = 0.0, ld = 1.0;
    bool rainon = true;
    uint slot, gid, gid_old = 0u;
    bool xfade = false;                  // crossfade frame of a changing string
    uint gxu = uint(u_atl.x);

    if (u_film == 0) {
        float d = h1(laneu, seed, 4u);
        float maxlen = %(TRAIL_MAX)f * u_lay1[L].x;
        float gap = extent * 0.6 / u_lay0[L].w;
        float period = extent + maxlen + gap;
        float pos = u_ptime * speed + d * period;
        // Slow per-lane speed drift (smooth, so strings never jump).
        if (u_run != 0u)
            pos += 8.0 * sin(u_ptime * mix(0.15, 0.5, h1(laneu, seed, 12u))
                             + 6.2831853 * h1(laneu, seed, 13u));
        float cyc = floor(pos / period);
        float ph = pos - cyc * period;
        uint cycu = uint(max(cyc, 0.0));
        float len = mix(%(TRAIL_MIN)f, %(TRAIL_MAX)f, h1(laneu, seed + 100u, cycu)) * u_lay1[L].x;
        float shift = gap * h1(laneu, seed + 200u, cycu);
        dist = (ph - shift) - a;
        bool inside = !(dist < 0.0 || dist > len);
        if (!inside) {
            if (msg == 0) return vec3(0.0);
            rainon = false;
        } else {
            br = pow(clamp(1.0 - dist / len, 0.0, 1.0), u_falloff);
            headness = clamp(1.0 - dist, 0.0, 1.0);
            float h = h1(laneu, seed + 800u, cycu);
            ld = clamp((u_live_density - h) / 0.1 + 1.0, 0.0, 1.0);
        }

        // Glyph identity: slowly mutates in the trail, flickers fast at the head.
        slot = uint(u_time * 0.35 + h1(uint(cr.x), uint(cr.y), seed + 300u) * 16.0);
        if (msg == 2 || (msg == 0 && inside && dist < 1.0)) slot = uint(u_time * 12.0) + 7777u;
        gid = uint(h1(cellu, slot, seed + 400u) * float(u_nglyph));
    } else {
        // Film sawtooth: one endless wobbling phase per lane.
        float dens = lane_dens(L, lane, seed, rows, cols);
        float pstr = 1.0;   // picture level along the string: bright at the head, fading up the trail
        float rstr = 0.0;   // the same for the rain through the subject (its own trail curve)
        float wk = 1.0;     // how white a head over the picture stays (see u_img_gwhite)
        bool lit = h1(laneu, seed, 7u) < ((u_run != 0u) ? 1.0 : dens);
        if (!lit && msg == 0 && !mcell && plv <= 0.0 && prm <= 0.0) return vec3(0.0);
        uint ku = 0u;
        float base = 0.0, ldf = 1.0;
        bool leader = false;
        float T = u_saw.x * u_lay1[L].x;
        if (fine) T /= csm.y;   // and the same trail length in pixels
        float o = h1(laneu, seed, 4u) * 1000.0;
        float w = 0.0, k = 0.0;
        float dfr = 0.0, dfp = 0.0;   // smooth per-lane speed drift (rain and pulse clocks)
        if (u_run != 0u) {
            float dw = mix(0.15, 0.5, h1(laneu, seed, 12u)), dp = 6.2831853 * h1(laneu, seed, 13u);
            dfr = 6.0 * sin(u_rain_time * dw + dp);
            dfp = 6.0 * sin(u_ptime * dw + dp);
        }
        // Head-latched letter: lit from the first head after the reveal to the first
        // head after the deletion, whether or not the lane carries rain of its own.
        bool mlat = false, mhead = false;
        float mglitch = -1.0;   // >= 0: a changed clock cell in its glitch, the flicker level
        if (mcell) {
            // Always-up clock, minute change: cells that stay keep their latch; new cells latch on
            // the first head of their own lane after the change, old ones stay until that head
            // passes; until then both flicker through the rain (only the changed cells).
            float rr = (mkind == 1 && u_msg_ch.x >= 0.0) ? u_msg_ch.x : u_msg_rt.x;
            float rd = (mkind == 2 && u_msg_ch.x >= 0.0) ? u_msg_ch.x : u_msg_rt.y;
            float wn = wobble(((u_rain_time + o) * speed + dfr - a) / T);
            float wr = wobble(((rr + o) * speed + lane_drift(rr, laneu, seed) - a) / T);
            // negative: never deleted (clock_fixed)
            float wd = (rd < 0.0) ? 1.0e9 : wobble(((rd + o) * speed + lane_drift(rd, laneu, seed) - a) / T);
            float kn = floor(wn), kr = floor(wr) + 1.0, kd = floor(wd) + 1.0;
            mlat = kn >= kr && kn < kd;
            mhead = mlat && kn == kr;
            if (mkind != 0 && u_msg_ch.x >= 0.0 && u_rain_time - u_msg_ch.x < u_msg_ch.y
                    && kn < (mkind == 1 ? kr : kd)) {
                float ft = floor(u_rain_time * 14.0);
                float on = h1(cellu, uint(ft + 65536.0), seed + 950u);
                float fade = 1.0 - (u_rain_time - u_msg_ch.x) / u_msg_ch.y;
                // old digits break up, new ones flash in
                mlat = on < (mkind == 2 ? 0.75 : 0.45) * (0.4 + 0.6 * fade);
                mglitch = mlat ? (0.3 + 0.55 * h1(cellu, uint(ft + 65536.0), seed + 951u)) : -1.0;
                mhead = false;
            }
            if (mlat) lit = true;
        }
        if (plv > 0.0 || prm > 0.0) lit = true;
        if (lit) {
            w = wobble(((u_rain_time + o) * speed + dfr - a) / T);
            k = floor(w);
            ku = uint(k + 65536.0);
            // Live churn: every lane is lit, and each string is kept with probability
            // dens, so the mean density is unchanged but the columns that carry rain
            // change string by string. Over the picture a dropped string leaves the cell at the level
            // kept between strings (it still shows the picture, but nothing falls through it).
            // grid exit hold: no main-layer string is dropped while the picture leaves, so the rain itself
            // replaces it in sparse lanes too (no picture held to the backstop and then cleared into a gap)
            bool xkeep = L == u_rip_lay && exit_window(k, o, speed, a, T, laneu, seed);
            if (u_run != 0u && !mlat && !xkeep && h1(laneu, seed + 900u, ku) >= dens) {
                if (plv > 0.0 || prm > 0.0) rdrop = true;
                else {
                    lit = false;
                    if (msg == 0 && !mcell) return vec3(0.0);
                }
            }
        }
        if (lit) {
            bool hl = h1(laneu, seed + 500u, ku) < u_lead;
            float b, b_ahead;
            if (hl) {   // highlighted strings follow the pulse clock
                float pt = (u_ptime + o) * speed + dfp;
                b = 1.0 - fract(wobble((pt - a) / T));
                b_ahead = 1.0 - fract(wobble((pt - a - 1.0) / T));
            } else {
                b = 1.0 - fract(w);
                b_ahead = 1.0 - fract(wobble(((u_rain_time + o) * speed + dfr - a - 1.0) / T));
            }
            pstr = rdrop ? 0.0 : pow(b, u_img_gsgam);
            rstr = rdrop ? 0.0 : pow(b, u_img_grain.y);   // the falling string's envelope: 1 at the head, 0 at the end of the trail
            // grid_hold entry: behind the head that brought it, the picture is lit by that string, handing over to its own rain
            if (mig < 1.0) pstr = mix(menv, pstr, mig);
            if (rdrop) base = 0.0;
            base = clamp(b * u_saw.y + u_saw.z, 0.0, 1.0);
            if (u_gamma != 1.0) base = pow(base, u_gamma);
            // grid exit hold (looks with gaps between strings, set per preset): every string on a lane while
            // the picture leaves keeps its whole tooth lit, fading to the next head instead of leaving a
            // black gap beside cells still holding the picture. Whole strings only: the gaps come back
            // with the first head after the window, so nothing is faded or cut.
            if (!rdrop && !hl && exit_window(k, o, speed, a, T, laneu, seed)) {
                float top = pow(clamp(u_saw.y + u_saw.z, 0.0, 1.0), u_gamma);
                base = max(base, top * pow(b, u_exit_hold));
            }
            if (base <= 0.0 && !phead) {
                if (msg == 0 && !mlat && plv <= 0.0 && prm <= 0.0) return vec3(0.0);
            } else {
                if (u_saw.w >= 0.0 && base > 0.0) base = u_saw.w;
                // over the picture every string's head lights up as it passes a lit cell, not only the arrival head
                bool pl = plv > 0.3;
                leader = (fine ? (phead || pl) : (hl || mhead || phead || pl)) && b > b_ahead;
                if (mig < 0.5) leader = false;   // grid_hold entry: the bringing string's own head leads, not the picture's
                // white heads over the picture, sparse and soft: in the picture passes only some lanes'
                // heads light, and only partly white; the main rain's heads dim to a faint white there.
                // The heads that bring the picture and the strings that take it away keep theirs.
                if (leader && !phead && preg) {
                    if (fine) {
                        if (h1(laneu, seed, 24u) >= u_img_gwhite.x) leader = false;
                        else wk = u_img_gwhite.y;
                    } else if (!pbring && !g_rev_exit && !exit_window(k, o, speed, a, T, laneu, seed)) wk = u_img_gwhite.z;
                }
                float h = h1(laneu, seed + 800u, ku);
                ldf = clamp((u_live_density - h) / 0.1 + 1.0, 0.0, 1.0);
            }
        }
        bool soft = leader && wk < 1.0;
        if (soft) leader = false;
        // A leader stays near-white.
        col_r = leader ? 0.0 : min(1.0, base * ldf * (fine ? 0.0 : ((preg && !g_rev_exit) ? u_img_gfloor : 1.0)));
        // the picture: max(rain, picture), the rain is never zeroed
        if (plv > 0.0 && !leader) {
            // the rain carries the picture: the cell's level (lane share, gain, clipped here so the string's
            // modulation survives) times the falling string's envelope, which keeps 1 - grid_string between strings
            float lanef = mix(1.0 - u_img_glane, 1.0, h1(laneu, seed, 21u));
            float lv = min(1.0, plv * lanef * u_img_gboost);
            // highlights (the brightest picture cells: lit windows, eyes) glow steadily, not only under a string
            float gstr = u_img_gstr * (1.0 - u_img_gglow * smoothstep(0.55, 0.95, plv));
            col_r = max(col_r, lv * mix(1.0, pstr, gstr) * u_msg_hold);
        }
        // rain through the subject and dripping below it: the string itself, on the picture's lanes
        // (down the faces, or along the perspective lines), whatever the picture's light there
        if (prm > 0.0 && !leader && h1(laneu, seed, 23u) < u_img_grain.z) col_r = max(col_r, prm * rstr * u_msg_hold);
        // letters read by a pale cursor tint
        col_g = leader ? ldf : ((mlat && mcell) ? %(MSG_WHITE)f : 0.0);
        if (soft) col_g = max(col_g, ldf * wk);
        if (mlat && !leader) col_r = max(col_r, u_msg_hold);
        // glitching clock cell: dimmer, no cursor tint
        if (mglitch >= 0.0 && !leader) { col_r = mglitch * u_msg_hold; col_g = 0.0; }

        // Glyph change. Message cells always use the unsynchronised rule;
        // a lane that is not lit has no tooth counter ku.
        float n = float(u_nglyph);
        float c = h1(uint(cr.x), uint(cr.y), seed + 300u);
        if (lit && u_cycle.z > 0.0 && msg == 0) {
            // picture cells change glyph when a string passes (slot ku), never on the shared clock
            bool changing = plv <= 0.0 && h1(laneu, seed + 600u, ku) < u_cycle.z;
            slot = changing ? uint(u_gslot) : ku;
            gid = uint(h1(cellu, slot, seed + 400u) * n);
            if (u_gmix > 0.0 && changing) {
                xfade = true;
                gid_old = min(uint(h1(cellu, uint(u_gprev), seed + 400u) * n), uint(u_nglyph - 1));
            }
        } else {
            slot = uint(floor(u_time / u_cycle.x + c));
            if (u_cycle.y > 0.5) {
                float c2 = h1(uint(cr.x), uint(cr.y), seed + 700u);
                gid = (uint(floor(c2 * n)) + slot) %% uint(u_nglyph);
            } else {
                gid = uint(h1(cellu, slot, seed + 400u) * n);
            }
        }
    }
    gid = min(gid, uint(u_nglyph - 1));
    float blur = 1.0 + u_lay1[L].y * 5.0;
    if (u_defocus > 0.0) blur = max(blur, u_defocus * cell.x);
    float g;
    float glint_cov = 0.0;
    if (u_set == 1) {   // resurrections tile; glint is read from this tap only
        uint gx2 = uint(u_atl2.x);
        vec2 gcell2 = vec2(float(gid %% gx2), float(gid / gx2));
        vec2 inner2 = vec2(1.0) - 2.0 * u_atl2.zw;
        vec2 uv2 = (gcell2 + u_atl2.zw + f * inner2) / u_atl2.xy;
        vec2 gx2v = vec2(inner2.x / (u_atl2.x * cell.x), 0.0) * blur * mgr.x;
        vec2 gy2v = vec2(0.0, inner2.y / (u_atl2.y * cell.y)) * blur * mgr.y;
        vec2 rg = textureGrad(u_atlas2, uv2, gx2v, gy2v).rg;
        g = rg.r;
        glint_cov = rg.g;
    } else {
        vec2 gcell = vec2(float(gid %% gxu), float(gid / gxu));
        vec2 inner = vec2(1.0) - 2.0 * u_atl.zw;
        vec2 uv = (gcell + u_atl.zw + f * inner) / u_atl.xy;
        vec2 gx = vec2(inner.x / (u_atl.x * cell.x), 0.0) * blur * mgr.x;
        vec2 gy = vec2(0.0, inner.y / (u_atl.y * cell.y)) * blur * mgr.y;
        g = (u_set == 2) ? textureGrad(u_atlas3, uv, gx, gy).r : textureGrad(u_atlas, uv, gx, gy).r;
        if (xfade) {   // one 50 percent frame of the old and new glyph
            vec2 ocell = vec2(float(gid_old %% gxu), float(gid_old / gxu));
            vec2 ouv = (ocell + u_atl.zw + f * inner) / u_atl.xy;
            float g_old = (u_set == 2) ? textureGrad(u_atlas3, ouv, gx, gy).r : textureGrad(u_atlas, ouv, gx, gy).r;
            g = (1.0 - u_gmix) * g + u_gmix * g_old;
        }
    }
    if (u_lay1[L].y > 0.0) g *= 1.25;  // keep defocused glyphs from vanishing

    if (u_film == 1) {
        vec2 fc = vec2(col_r, col_g);
        if (u_glint > 0.0 && glint_cov > 0.0 && col_g == 0.0 && col_r > 0.0)
            fc.x = min(1.0, fc.x + u_glint * glint_cov);
        if (msg == 1) fc = max(fc, vec2(1.0, 0.0));
        else if (msg == 2) fc = max(fc, vec2(0.0, 1.0));
        return vec3(fc, 0.0) * g * ldim;
    }
    vec3 col = rainon ? mix(u_base * br, u_head, headness) * ld : vec3(0.0);
    if (msg == 1) col = max(col, u_base);
    else if (msg == 2) col = max(col, u_head);
    return col * g * ldim;
}

// Structure tensor of the picture around a cell (5x5 taps, 3x3 central-difference gradients):
// x = how far the dominant edge direction is from the nearest axis (radians, -pi/4..pi/4), y = coherence 0..1.
vec2 img_orient(sampler2D tex, vec2 isize, vec2 c, vec2 cell, vec2 ms) {
    float h = cell.y * 0.7;
    float lod = log2(max(1.0, h * isize.y / ms.y));
    float L[25];
    for (int j = 0; j < 5; j++)
        for (int i = 0; i < 5; i++)
            L[j * 5 + i] = textureLod(tex, img_cover((c + vec2(float(i - 2), float(j - 2)) * h) / ms, isize, ms), lod).r;
    float jxx = 0.0, jxy = 0.0, jyy = 0.0;
    for (int j = 1; j < 4; j++)
        for (int i = 1; i < 4; i++) {
            float gx = L[j * 5 + i + 1] - L[j * 5 + i - 1], gy = L[(j + 1) * 5 + i] - L[(j - 1) * 5 + i];
            jxx += gx * gx; jxy += gx * gy; jyy += gy * gy;
        }
    float tr = jxx + jyy, dd = length(vec2(jxx - jyy, 2.0 * jxy));
    float coh = dd / (tr + 1e-6) * smoothstep(0.002, 0.03, tr);
    // gradient direction; the edge is 90 degrees off, same deviation from the axes
    float phi = 0.5 * atan(2.0 * jxy, jxx - jyy);
    float dev = phi - floor(phi / 1.5707963 + 0.5) * 1.5707963;
    return vec2(dev, coh);
}


// The image (any picture) as its own glyph grid, brightness from the picture (edges and surface texture
// bright, dark areas empty). With a confident vanishing point the grid is the perspective box
// above; otherwise one of three flat octave grids chosen by a fake depth. A glyph shows once
// the first head after the image's start has landed on the main-grid cell that contains it.
vec2 img_glyphs(vec2 mp, vec2 ms, float dpi, int mi) {
    int L = u_rip_lay;
    float sc = u_lay0[L].x * dpi * u_gscale;
    vec2 mcell_ = floor(vec2(%(CELL_W)f, %(CELL_H)f) * sc + 0.5);
    if (u_cols > 0.0) mcell_ = vec2(max(4.0, floor(ms.x / u_cols * u_lay0[L].x * u_gscale + 0.5)));
    float age;
    vec2 rp = image_reveal_a(clamp(mp, vec2(0.0), ms - 1.0), ms, dpi, mi, age);
    // just behind the head the glyphs are big and sharply tilted, and settle to their depth as the head moves on
    float tr = (u_img_settle.x > 0.0 && (u_img_par == 0 ? rp.x : rp.y) > 0.0) ? exp(-age / u_img_settle.x) : 0.0;
    if (rp.x + rp.y == 0.0) return vec2(0.0);
    // How far the rain has stepped back here. It follows the pixel's own rain cell and eases in
    // over the rows behind the head (a picture swept over by the next one is fully clear), so a
    // big rain glyph fades across its height instead of being cut at an image cell edge.
    float cover = (u_img_par == 0 ? rp.y : rp.x) > 0.0 ? 1.0 : smoothstep(0.0, 10.0, age);
    bool useA = rp.x > 0.0;
    vec2 isz = useA ? u_img_size0 : u_img_size1;
    vec3 ivp = useA ? u_img_vp0 : u_img_vp1;
    float minpx = max(u_img_detail.x, floor(mcell_.y * u_img_oct.z + 0.5));
    float nearS = 0.0;
    vec2 g, cc, cell;
    int reg;
    if (u_img_persp.x > 0.0 && ivp.z > 0.5) {
        g_radial = ivp.z > 1.5;
        g_pkind = img_label(useA, mp, ms);
        vec2 vpm = img_uncover(ivp.xy, isz, ms) * ms;
        // young glyphs: a little bigger and nearer (kept small so they never read as big rain glyphs)
        float grow = 1.0 + 0.5 * u_img_settle.y * tr;
        img_persp(mp, ms, vpm, mcell_ * u_img_persp.z * grow, max(floor(mcell_ * u_img_oct.z * grow + 0.5), vec2(u_img_detail.x)), minpx, vec2(0.0), vec2(0.0), g, cc, cell, reg);
        if (cc.x < 0.0 || cc.y < 0.0 || cc.x >= ms.x || cc.y >= ms.y) return vec2(0.0, cover);
    } else if ((useA ? u_img_fv0.z : u_img_fv1.z) >= 0.0) {
        // depth field: rows and columns from the per-image tables, the glyph size follows each surface
        vec4 fv = useA ? u_img_fv0 : u_img_fv1;
        vec2 ic = img_cover(mp / ms, isz, ms);
        float sr = (isz.x / isz.y) / (ms.x / ms.y);
        float kpx = sr > 1.0 ? ms.y : ms.y / sr;          // screen px per image height
        float grow = 1.0 + 0.5 * u_img_settle.y * tr;     // young glyphs: a little bigger
        vec2 mc = mcell_ * grow;
        vec3 F = useA ? texture(u_imgf0, ic).rgb : texture(u_imgf1, ic).rgb;
        float v = F.r * kpx / mc.y;
        float Vc = (floor(v) + 0.5) * mc.y / kpx;
        float nv = float(useA ? textureSize(u_imgf0, 0).y : textureSize(u_imgf1, 0).y);
        float tv = (clamp((Vc - fv.x) / max(fv.y - fv.x, 1e-6), 0.0, 1.0) * (nv - 1.0) + 0.5) / nv;
        float U = useA ? texture(u_imgf0, vec2(ic.x, tv)).g : texture(u_imgf1, vec2(ic.x, tv)).g;
        g = vec2(U * kpx / mc.x, v);
        cell = max(F.b * mc, vec2(2.0));
        nearS = F.b;
        reg = 7;
        cc = mp + (floor(g) + 0.5 - g) * cell;
        if (cc.x < 0.0 || cc.y < 0.0 || cc.x >= ms.x || cc.y >= ms.y) return vec2(0.0, cover);
    } else {
        // fake depth at this pixel: far from the vanishing point = near the viewer (big glyphs), fine texture = far (small)
        vec2 ic0 = img_cover(mp / ms, isz, ms);
        float lodm = log2(max(1.0, mcell_.y * u_img_oct.y * isz.y / ms.y));
        float rough = abs((useA ? textureLod(u_img0, ic0, lodm).r - textureLod(u_img0, ic0, lodm + 2.0).r
                                : textureLod(u_img1, ic0, lodm).r - textureLod(u_img1, ic0, lodm + 2.0).r));
        vec2 dv = (ic0 - ivp.xy) * vec2(isz.x / isz.y, 1.0);
        float near = smoothstep(0.15, 1.0, length(dv));
        float dep = clamp(0.8 * near + 0.2 * (1.0 - clamp(rough * 8.0, 0.0, 1.0)) + u_img_depthbias + tr * u_img_settle.y, 0.0, 1.0);
        int oct = dep > 0.66 ? 0 : (dep > 0.36 ? 1 : 2);
        reg = 4 + oct;
        cell = max(floor(mcell_ * u_img_oct[oct] + 0.5), vec2(u_img_detail.x));
        float cols = floor(ms.x / cell.x), rows = floor(ms.y / cell.y);
        float padx = floor((ms.x - cols * cell.x) * 0.5);
        vec2 q = vec2(mp.x - padx, mp.y);
        if (q.x < 0.0 || q.x >= cols * cell.x || q.y >= rows * cell.y) return vec2(0.0, cover);
        g = q / cell;
        cc = vec2(padx, 0.0) + (floor(g) + 0.5) * cell;
    }
    vec2 cr = floor(g), f = g - cr;
    vec2 dgx = dFdx(g), dgy = dFdy(g);
    // U jumps between rows: use the cell size
    if (reg == 7) { dgx = vec2(1.0 / cell.x, 0.0); dgy = vec2(0.0, 1.0 / cell.y); }
    // drawn and dimmed by the pixel's own rain lane, not the lane of the glyph cell's centre, so a
    // glyph cell straddling two lanes never leaves a dark strip in a lane that is already revealed
    vec2 rv = rp;
    if (rv.x + rv.y == 0.0) return vec2(0.0, cover);
    // Where the picture is open (sky) or dark the rain keeps part of its brightness instead of
    // leaving an empty box; it is read from the blurred picture, so it never speckles by cell.
    vec2 bic = img_cover(cc / ms, rv.x > 0.0 ? u_img_size0 : u_img_size1, ms);
    vec2 bl = (rv.x > 0.0) ? textureLod(u_img0, bic, 4.0).rg : textureLod(u_img1, bic, 4.0).rg;
    // Sky and shadow are not left to the big rain glyphs (a hard-edged patch of them reads as an
    // artefact); they get a sparse floor of picture-scale glyphs instead, below.
    float back = max(0.5 * bl.g, 0.35 * (1.0 - smoothstep(0.02, 0.15, bl.r)));
    vec2 res = vec2(0.0, cover);   // y: this spot is revealed, so the rain's own glyphs step back
    uint seed = uint(L * 64 + mi * 8 + 5 + reg * 977);
    uint cx = uint(int(cr.x) + 65536), cy = uint(int(cr.y) + 65536);
    float lv;
    if (u_img_surf.x > 0.0) {
        vec3 q = (rv.x > 0.0) ? img_surface(u_img0, u_img_size0, cc, cell, ms) : img_surface(u_img1, u_img_size1, cc, cell, ms);
        // the share of lit cells follows tone, stable per cell
        float lit = step(h1(cx, cy, seed + 330u), q.z);
        lv = max(q.x * lit, q.y);
    } else {
        lv = (rv.x > 0.0) ? img_level(u_img0, u_img_size0, cc, cell, ms) : img_level(u_img1, u_img_size1, cc, cell, ms);
        lv = pow(smoothstep(u_img_dim, 0.9, lv), 1.4);
    }
    // near ground and water: a dim floor so their big glyphs show
    if (reg == 7 && u_img_nfill.x > 0.0 && u_img_surf.x <= 0.0) {
        vec2 icc = img_cover(cc / ms, rv.x > 0.0 ? u_img_size0 : u_img_size1, ms);
        float lc = (rv.x > 0.0) ? textureLod(u_img0, icc, 4.0).r : textureLod(u_img1, icc, 4.0).r;
        lv = max(lv, u_img_nfill.x * smoothstep(u_img_nfill.y, u_img_nfill.z, nearS) * smoothstep(0.02, 0.15, lc));
    }
    lv = max(lv, 0.7 * back * step(0.5, h1(cx, cy, seed + 340u)));
    if (lv <= 0.0) return res;
    float hc = h1(cx, cy, seed + 300u);
    // glyphs keep changing, each cell on its own beat
    uint slot = uint(floor(u_time * 2.2 + hc * 9.0));
    float hl = h1(cx, 0u, seed + 310u), hs = h1(cx, 0u, seed + 311u);
    // streaks of brightness run down the image lane by lane, like the rain through it
    float ph = fract(cr.y * 0.028 - u_time * (0.45 + 0.9 * hs) + hl * 9.0);
    float streak = mix(u_img_move, 1.0, pow(ph, 2.5)) + 0.6 * u_img_move * smoothstep(0.97, 1.0, ph);
    // per-cell flicker, re-rolled nine times a second
    float shim = 1.0 - 0.3 * u_img_move * h1(cx * 7u + cy, uint(floor(u_time * 9.0)), seed + 320u);
    uint gid = min(uint(h1(cx * 4099u + cy, slot, seed + 400u) * float(u_nglyph)), uint(u_nglyph - 1));
    uint gxu = uint(u_atl.x);
    vec2 gcell = vec2(float(gid %% gxu), float(gid / gxu));
    vec2 inner = vec2(1.0) - 2.0 * u_atl.zw;
    // flat grids and the back wall: the glyph follows the local surface direction, rotated by the
    // edge deviation from the axes, scaled by coherence (walls and floor already follow the perspective)
    float ang = 0.0;
    if (reg == 0 || reg >= 4) {
        vec2 po = (rv.x > 0.0) ? img_orient(u_img0, u_img_size0, cc, cell, ms) : img_orient(u_img1, u_img_size1, cc, cell, ms);
        // young glyphs lean harder
        ang = po.x * clamp(po.y * 1.6 + tr, 0.0, 1.0) * u_img_orient * (1.0 + 1.5 * tr);
    }
    float ca = cos(ang), sa = sin(ang);
    vec2 pq = (f - 0.5) * cell;
    // inverse rotation, grown so the turned glyph still fits the cell
    pq = vec2(ca * pq.x + sa * pq.y, -sa * pq.x + ca * pq.y) / cell * (abs(ca) + abs(sa));
    vec2 fr = pq + 0.5;
    float inside = (fr.x >= 0.0 && fr.x <= 1.0 && fr.y >= 0.0 && fr.y <= 1.0) ? 1.0 : 0.0;
    vec2 uv = (gcell + u_atl.zw + clamp(fr, 0.0, 1.0) * inner) / u_atl.xy;
    vec2 k = inner / u_atl.xy * (abs(ca) + abs(sa));
    vec2 gx = clamp(dgx, -1.0, 1.0) * k, gy = clamp(dgy, -1.0, 1.0) * k;
    float gl = inside * ((u_set == 2) ? textureGrad(u_atlas3, uv, gx, gy).r : textureGrad(u_atlas, uv, gx, gy).r);
    return vec2(min(1.0, gl * (abs(ca) + abs(sa)) * lv * u_msg_hold * 1.2 * streak * shim * (0.4 + 0.6 * cover)), cover);
}

// Sparse large soft particles drifting down over the picture (the film's snow). Each is a soft
// disc well inside its own cell, so it is never clipped; the grid of cells drifts per column.
float grid_particles(vec2 mp, float dpi, vec2 ms, bool useA) {
    float P = 100.0 * dpi;
    float cx = floor(mp.x / P);
    float vy = mix(8.0, 22.0, h1(uint(cx), 31u, 7u)) * dpi;
    float y = mp.y - u_time * vy;
    float cyf = floor(y / P);
    uint ix = uint(cx + 4096.0), iy = uint(cyf + 65536.0);
    if (h1(ix, iy, 11u) >= u_img_gpart.x) return 0.0;
    vec2 ctr = (vec2(cx, cyf) + vec2(0.3 + 0.4 * h1(ix, iy, 12u), 0.3 + 0.4 * h1(ix, iy, 13u))) * P;
    // only on the picture's own lit glyph areas: the particle's centre (in screen space) must sit on
    // a lit part of the picture, and it is bigger on near parts (depth) than on far ones
    float disp, tone;
    vec2 sc = vec2(ctr.x, ctr.y + u_time * vy);
    if (img_label(useA, sc, ms, disp, tone) < 0 || tone < 0.0) return 0.0;
    float lit = smoothstep(0.25, 0.55, tone * mix(0.5, 1.0, clamp(disp, 0.0, 1.0)));
    if (lit <= 0.0) return 0.0;
    float r = P * (0.04 + 0.07 * h1(ix, iy, 14u)) * (0.35 + 1.1 * clamp(disp, 0.0, 1.0));
    float d = length(vec2(mp.x, y) - ctr) / r;
    return lit * u_img_gpart.y * (0.45 + 0.55 * h1(ix, iy, 15u)) * exp(-d * d * 1.6);
}

// The message on its own finer glyph grid, drawn over the rain (film encoding: x brightness, y leader).
// Cells light from a reveal front that steps one fine cell at a time (the main grid's reveal timing, a
// jitter per fine lane) and go out with the deletion front. The always-up clock after a minute change
// keeps the cells that stay, lights the new ones as the front reaches them and drops the old ones then.
vec3 msg_fine(vec2 mp, vec2 ms, int mi) {
    vec4 box = u_msg_fbox[mi];
    vec2 cell = u_msg_fcell[mi];
    float cols = floor(ms.x / cell.x), rows = floor(ms.y / cell.y);
    float padx = floor((ms.x - cols * cell.x) * 0.5);
    vec2 q = vec2(mp.x - padx, mp.y);
    if (q.x < 0.0 || q.x >= cols * cell.x || q.y >= rows * cell.y) return vec3(0.0);
    vec2 cr = floor(q / cell);
    vec2 f = q / cell - cr;
    if (cr.x < box.x || cr.x >= box.x + box.z || cr.y < box.y || cr.y >= box.y + box.w) return vec3(0.0);
    float mv = texelFetch(u_msg, ivec2(int(cr.x - box.x), int(u_msg_off[mi] + cr.y - box.y)), 0).r;
    if (mv < 0.25) return vec3(0.0);
    // change codes: 1.0 stays, 0.75 appears, 0.38 vanishes
    int kind = mv > 0.9 ? 0 : (mv > 0.5 ? 1 : 2);
    float lane = cr.x, a = cr.y, a0 = box.y;
    if (u_dirmode == 1) { lane = cr.y; a = cr.x; a0 = box.x; }
    else if (u_dirmode == 2) lane = cr.x - cr.y + rows;
    uint laneu = uint(lane);
    float j1 = h1(laneu, uint(mi) * 16u + 902u, uint(u_msg_n));
    float j2 = h1(laneu, uint(mi) * 16u + 903u, uint(u_msg_n));
    float fr = floor(a0 - 4.0 * j1 + (u_time - u_msg_t.x - 0.6 * j2) * 30.0);
    float de = floor(a0 - 4.0 * j1 + (u_time - u_msg_t.y - 0.6 * j2) * 30.0);
    int msg = 0;   // 1 lit, 2 leader
    if (u_msg_ch.x >= 0.0) {
        if (kind == 0) msg = 1;
        else if (kind == 1) { if (fr >= a) msg = (fr == a) ? 2 : 1; }
        else if (fr < a) msg = 1;
    } else if (fr >= a && de < a) msg = (fr == a) ? 2 : 1;
    if (msg == 0) return vec3(0.0);

    int L = u_msg_lay[mi];
    uint seed = uint(L * 64 + mi * 8 + 1);
    uint cellu = uint(cr.x) * 4099u + uint(cr.y);
    float n = float(u_nglyph);
    float c = h1(uint(cr.x), uint(cr.y), seed + 300u);
    uint slot = (msg == 2) ? uint(u_time * 12.0) + 7777u : uint(floor(u_time / u_cycle.x + c));
    uint gid;
    if (msg != 2 && u_cycle.y > 0.5) {
        float c2 = h1(uint(cr.x), uint(cr.y), seed + 700u);
        gid = (uint(floor(c2 * n)) + slot) %% uint(u_nglyph);
    } else {
        gid = uint(h1(cellu, slot, seed + 400u) * n);
    }
    gid = min(gid, uint(u_nglyph - 1));
    float blur = 1.0 + u_lay1[L].y * 5.0;
    if (u_defocus > 0.0) blur = max(blur, u_defocus * cell.x);
    float g;
    if (u_set == 1) {
        uint gx2 = uint(u_atl2.x);
        vec2 gcell2 = vec2(float(gid %% gx2), float(gid / gx2));
        vec2 inner2 = vec2(1.0) - 2.0 * u_atl2.zw;
        vec2 uv2 = (gcell2 + u_atl2.zw + f * inner2) / u_atl2.xy;
        vec2 gx2v = vec2(inner2.x / (u_atl2.x * cell.x), 0.0) * blur;
        vec2 gy2v = vec2(0.0, inner2.y / (u_atl2.y * cell.y)) * blur;
        g = textureGrad(u_atlas2, uv2, gx2v, gy2v).r;
    } else {
        uint gxu = uint(u_atl.x);
        vec2 gcell = vec2(float(gid %% gxu), float(gid / gxu));
        vec2 inner = vec2(1.0) - 2.0 * u_atl.zw;
        vec2 uv = (gcell + u_atl.zw + f * inner) / u_atl.xy;
        vec2 gx = vec2(inner.x / (u_atl.x * cell.x), 0.0) * blur;
        vec2 gy = vec2(0.0, inner.y / (u_atl.y * cell.y)) * blur;
        g = (u_set == 2) ? textureGrad(u_atlas3, uv, gx, gy).r : textureGrad(u_atlas, uv, gx, gy).r;
    }
    if (u_lay1[L].y > 0.0) g *= 1.25;
    float ldim = u_lay0[L].y;
    if (u_film == 1) return vec3(msg == 2 ? vec2(0.0, 1.0) : vec2(u_msg_hold, %(MSG_WHITE)f), 0.0) * g * ldim;
    return (msg == 2 ? u_head : u_base) * g * ldim;
}

void main() {
    if (STAGE == 1 && u_rev_pass == 1) {   // reveal cache pre-pass: one fragment per main-layer cell
        ivec2 fc = ivec2(gl_FragCoord.xy);
        int mi = fc.y / u_rev_rh;
        vec4 o = vec4(0.0);
        if (mi < u_nmon) {
            vec2 cell;
            float cols, rows, padx;
            rev_grid(u_mon[mi].zw, u_dpi[mi], cell, cols, rows, padx);
            vec2 cr = vec2(float(fc.x), float(fc.y - mi * u_rev_rh));
            if (cr.x < cols && cr.y < rows) {
                float age;
                bool head;
                vec2 rv = image_reveal_cell(cr, rows, cols, mi, age, head);
                o = vec4(rv, age, (head ? 1.0 : 0.0) + (g_rev_byhead ? 2.0 : 0.0) + (g_rev_exit ? 4.0 : 0.0));
            }
        }
        o_col = o;
        return;
    }
    vec2 p = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y);
    vec3 c = vec3(0.0);
    for (int m = 0; m < u_nmon; m++) {
        vec4 r = u_mon[m];
        if (p.x >= r.x && p.x < r.x + r.z && p.y >= r.y && p.y < r.y + r.w) {
            vec2 mp = p - r.xy;
            // grid mode: the depth layers' rain steps back where the picture is revealed
            float gk = 1.0;
            if (u_img_on != 0 && u_img_grid == 1 && u_film == 1 && u_dirmode == 0) {
                vec2 gv = image_reveal_a(mp, r.zw, u_dpi[m], m, g_mig_age);
                g_mig_rv = gv;
                g_mig_by = g_rev_byhead;
                gk = mix(1.0, u_img_gback, min(gv.x + gv.y, 1.0));
            }
            if (STAGE == 2) {   // the grid picture passes alone, screened onto the rain by the blend
                if (u_img_on != 0 && u_img_grid == 1 && u_img_gscale.y < 1.0 && u_film == 1 && u_dirmode == 0) {
                    if (u_img_gdepth > 0.5) {   // one picture pass per depth class, each at its own cell size
                        {
                            vec3 l = min(layer_color(u_rip_lay, mp, r.zw, u_dpi[m], m, u_img_gs1, -2), vec3(1.0));
                            c = c + l - c * l;
                        }
                        for (int k = 0; k < 3; k++) {
                            vec3 l = min(layer_color(u_rip_lay, mp, r.zw, u_dpi[m], m, k == 0 ? u_img_gs0 : (k == 1 ? u_img_gs1 : u_img_gs2), k), vec3(1.0));
                            c = c + l - c * l;
                        }
                        if (u_img_gedgep.x > 0.0) {
                            vec3 l = min(layer_color(u_rip_lay, mp, r.zw, u_dpi[m], m, u_img_gs1 * u_img_gedgep.x, 3), vec3(1.0));
                            c = c + l - c * l;
                        }
                    } else {
                        vec3 l = min(layer_color(u_rip_lay, mp, r.zw, u_dpi[m], m, u_img_gscale, -1), vec3(1.0));
                        c = c + l - c * l;
                    }
                }
                o_col = vec4(c, 0.0);
                return;
            }
            if (u_slices > 0.5) {   // screen blend of the depth slices
                for (int L = 0; L < u_nlay; L++) {
                    vec3 l = min(layer_color(L, mp, r.zw, u_dpi[m], m, vec2(1.0), -1) * (L == u_rip_lay ? 1.0 : gk), vec3(1.0));
                    c = c + l - c * l;
                }
            } else {
                for (int L = 0; L < u_nlay; L++)
                    c += layer_color(L, mp, r.zw, u_dpi[m], m, vec2(1.0), -1) * (L == u_rip_lay ? 1.0 : gk);
            }
            if (STAGE == 1 && u_msg_on == 1 && u_msg_fbox[m].z > 0.0) {
                vec3 ml = min(msg_fine(mp, r.zw, m), vec3(1.0));
                if (u_film == 1) c = c + ml - c * ml;
                else c += ml;
            }
            if (u_img_on != 0 && u_img_grid == 1 && u_film == 1 && u_dirmode == 0 && u_img_gpart.x > 0.0) {
                vec2 pgv = image_reveal(mp, r.zw, u_dpi[m], m);
                float pb = pgv.x + pgv.y > 0.0 ? grid_particles(mp, u_dpi[m], r.zw, pgv.x > 0.0) : 0.0;
                c.r = c.r + pb - c.r * pb;
                c.g = max(c.g, 0.6 * pb);
            }
            if (u_img_on != 0 && u_img_grid == 0 && u_film == 1 && u_dirmode == 0) {
                vec2 ig = img_glyphs(mp, r.zw, u_dpi[m], m);
                // the rain's own big glyphs and heads step back where the image is revealed (brightness only)
                float keep = mix(1.0, u_img_rain, ig.y);
                float rr = c.r * keep;
                c.r = rr + ig.x - rr * ig.x;   // screen: picture glyphs show through big rain glyphs
                c.g *= keep;
            }
            break;
        }
    }
    if (u_img_on != 0 && u_film == 1 && u_dirmode == 0) {
        for (int m = 0; m < u_nmon; m++) {
            vec4 r = u_mon[m];
            if (p.x >= r.x && p.x < r.x + r.z && p.y >= r.y && p.y < r.y + r.w) {
                vec2 iv = image_reveal(p - r.xy, r.zw, u_dpi[m], m);
                o_col = vec4(c.rg, iv);
                return;
            }
        }
    }
    o_col = vec4(c, 1.0);
}
