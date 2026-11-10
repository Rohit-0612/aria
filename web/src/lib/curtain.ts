/*
  The paper curtain — a full-screen sheet of newsprint with ripped edges,
  drawn by one fragment shader on a single triangle.

    uIn  0 → 1  the leading (bottom) torn edge sweeps down and covers the app
    uOut 0 → 1  the trailing (top) torn edge follows it and uncovers the app

  It is the page-turn of the broadsheet: the cover lifts off through it, a new
  consultation is a fresh sheet torn across the old one, and switching between
  the Day and Night editions tears the page over in the other ink.

  Plain WebGL, no library — it is a dozen calls. Without WebGL, or under
  reduced motion, a flat sheet slides or fades instead.
*/

const VERTEX = `
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT = `
precision highp float;
varying vec2 vUv;
uniform float uIn;
uniform float uOut;
uniform float uAspect;
uniform float uSeed;
uniform vec3 uColor;
uniform vec3 uCore;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

// Height of a torn edge for a given progress: a bow, a tilt, a rip, teeth.
float tornEdge(float x, float prog, float seed) {
  float A = 0.2;
  float bow = sin(x * 3.14159) * 0.11 * sin(prog * 3.14159);
  float tilt = (x - 0.5) * 0.06 * sin(prog * 3.14159);
  float rip = (fbm(vec2(x * 7.0 * uAspect, seed)) - 0.5) * 0.085;
  float teeth = (noise(vec2(x * 70.0 * uAspect, seed * 3.1)) - 0.5) * 0.014;
  return 1.0 + A - prog * (1.0 + 2.0 * A) + bow + tilt + rip + teeth;
}

void main() {
  vec2 uv = vUv;
  float lead = tornEdge(uv.x, uIn, uSeed);
  float trail = tornEdge(uv.x, uOut, uSeed + 11.7);
  bool covered = uv.y > lead && uv.y < trail;

  if (!covered) {
    // A soft cast shadow just beyond each moving edge.
    float s1 = (uv.y <= lead && uIn > 0.001 && uIn < 0.999) ? smoothstep(0.07, 0.0, lead - uv.y) : 0.0;
    float s2 = (uv.y >= trail && uOut > 0.001 && uOut < 0.999) ? smoothstep(0.05, 0.0, uv.y - trail) : 0.0;
    gl_FragColor = vec4(0.0, 0.0, 0.0, max(s1, s2) * 0.22);
    return;
  }

  vec2 p = uv * vec2(uAspect, 1.0);
  float blot = fbm(p * 3.0 + uSeed);
  float fibre = noise(vec2(p.x * 220.0, p.y * 14.0) + uSeed) * noise(vec2(p.x * 14.0, p.y * 260.0));
  float grain = hash(p * 900.0 + uSeed);
  vec3 col = uColor * (0.95 + 0.07 * blot) + (fibre - 0.25) * 0.012 + (grain - 0.5) * 0.03;

  // The torn, paler core of the paper along each ripped edge.
  float wLead = 0.006 + fbm(vec2(uv.x * 40.0 * uAspect, uSeed + 3.0)) * 0.02;
  float wTrail = 0.006 + fbm(vec2(uv.x * 40.0 * uAspect, uSeed + 9.0)) * 0.02;
  float dLead = uv.y - lead;
  float dTrail = trail - uv.y;
  float core = max(smoothstep(wLead, wLead * 0.35, dLead), smoothstep(wTrail, wTrail * 0.35, dTrail));
  core *= 0.75 + 0.25 * hash(floor(uv * vec2(900.0 * uAspect, 900.0)));
  col = mix(col, uCore * (0.95 + 0.05 * grain), core);

  // The sheet darkens a touch where it lifts off the page.
  float lift = smoothstep(0.08, 0.0, min(dLead, dTrail)) * 0.08;
  col *= 1.0 - lift * (1.0 - core);

  gl_FragColor = vec4(col, 1.0);
}
`;

type RGB = [number, number, number];

/** Resolve a design token (e.g. `--page`) to linear 0–1 RGB. */
export function tokenRGB(token: string): RGB {
  const probe = document.createElement('span');
  probe.style.color = `hsl(var(${token}))`;
  probe.style.display = 'none';
  document.body.appendChild(probe);
  const m = getComputedStyle(probe).color.match(/[\d.]+/g) ?? ['0', '0', '0'];
  probe.remove();
  return [Number(m[0]) / 255, Number(m[1]) / 255, Number(m[2]) / 255];
}

const toCss = ([r, g, b]: RGB) =>
  `rgb(${Math.round(r * 255)} ${Math.round(g * 255)} ${Math.round(b * 255)})`;
const luminance = ([r, g, b]: RGB) => 0.299 * r + 0.587 * g + 0.114 * b;

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

class Curtain {
  private gl: WebGLRenderingContext | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private fallback: HTMLDivElement | null = null;
  private label: HTMLDivElement | null = null;
  private loc: Record<string, WebGLUniformLocation | null> = {};
  private state = { in: 0, out: 0 };
  private color: RGB = [0.9, 0.88, 0.84];
  private seed = Math.random() * 10;
  private raf = 0;
  private busy = false;
  private pendingCovered = false;

  mount(canvas: HTMLCanvasElement, fallback: HTMLDivElement, label: HTMLDivElement) {
    if (this.canvas === canvas) return;
    this.canvas = canvas;
    this.fallback = fallback;
    this.label = label;
    try {
      const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false, antialias: false });
      if (!gl) throw new Error('no webgl');
      const shader = (type: number, src: string) => {
        const s = gl.createShader(type)!;
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? 'shader');
        return s;
      };
      const prog = gl.createProgram()!;
      gl.attachShader(prog, shader(gl.VERTEX_SHADER, VERTEX));
      gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FRAGMENT));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error('link');
      gl.useProgram(prog);

      // One triangle that over-covers the clip square.
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const pos = gl.getAttribLocation(prog, 'position');
      gl.enableVertexAttribArray(pos);
      gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.clearColor(0, 0, 0, 0);

      for (const u of ['uIn', 'uOut', 'uAspect', 'uSeed', 'uColor', 'uCore'])
        this.loc[u] = gl.getUniformLocation(prog, u);
      this.gl = gl;
    } catch {
      this.gl = null;
    }
    window.addEventListener('resize', this.resize);
    this.resize();
    if (this.pendingCovered) this.setCovered(this.color);
  }

  unmount() {
    window.removeEventListener('resize', this.resize);
    cancelAnimationFrame(this.raf);
    this.canvas = null;
    this.gl = null;
  }

  get isBusy() {
    return this.busy;
  }

  private resize = () => {
    const c = this.canvas;
    if (!c) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    c.width = Math.round(window.innerWidth * dpr);
    c.height = Math.round(window.innerHeight * dpr);
    this.gl?.viewport(0, 0, c.width, c.height);
    this.render();
  };

  private render = () => {
    const gl = this.gl;
    if (!gl || !this.canvas) return;
    const [r, g, b] = this.color;
    // A sheet printed in ink tears to a lighter core; newsprint, to a paler one.
    const core: RGB = [r + (1 - r) * 0.22, g + (1 - g) * 0.22, b + (1 - b) * 0.22];
    gl.uniform1f(this.loc.uIn, this.state.in);
    gl.uniform1f(this.loc.uOut, this.state.out);
    gl.uniform1f(this.loc.uAspect, this.canvas.width / Math.max(1, this.canvas.height));
    gl.uniform1f(this.loc.uSeed, this.seed);
    gl.uniform3f(this.loc.uColor, r, g, b);
    gl.uniform3f(this.loc.uCore, core[0], core[1], core[2]);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };

  private tween(key: 'in' | 'out', to: number, seconds: number) {
    cancelAnimationFrame(this.raf);
    const from = this.state[key];
    const t0 = performance.now();
    return new Promise<void>((resolve) => {
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / (seconds * 1000));
        this.state[key] = from + (to - from) * easeInOut(t);
        this.render();
        if (t < 1) this.raf = requestAnimationFrame(step);
        else resolve();
      };
      this.raf = requestAnimationFrame(step);
    });
  }

  private useFallback() {
    return !this.gl || reducedMotion();
  }

  /** Paint the screen fully covered, without animating. */
  setCovered(color: RGB) {
    this.color = color;
    this.state = { in: 1, out: 0 };
    if (!this.canvas) {
      this.pendingCovered = true;
      return;
    }
    this.pendingCovered = false;
    if (this.useFallback() && this.fallback) {
      this.fallback.style.background = toCss(color);
      this.fallback.style.transform = 'translateY(0)';
      this.fallback.style.opacity = '1';
    }
    this.render();
  }

  cover(color: RGB, seconds = 0.95): Promise<void> {
    this.color = color;
    this.seed = Math.random() * 10;
    this.state = { in: 0, out: 0 };
    const f = this.fallback;
    if (this.useFallback()) {
      if (!f) return Promise.resolve();
      f.style.background = toCss(color);
      const rm = reducedMotion();
      return f
        .animate(
          rm
            ? [{ opacity: 0 }, { opacity: 1 }]
            : [{ transform: 'translateY(-100%)', opacity: 1 }, { transform: 'translateY(0)', opacity: 1 }],
          { duration: rm ? 250 : seconds * 800, easing: 'cubic-bezier(0.65,0,0.35,1)', fill: 'forwards' },
        )
        .finished.then(() => undefined);
    }
    return this.tween('in', 1, seconds);
  }

  reveal(seconds = 1.2): Promise<void> {
    const f = this.fallback;
    if (this.useFallback()) {
      this.state = { in: 0, out: 0 };
      this.render();
      if (!f) return Promise.resolve();
      const rm = reducedMotion();
      return f
        .animate(
          rm
            ? [{ opacity: 1 }, { opacity: 0 }]
            : [{ transform: 'translateY(0)', opacity: 1 }, { transform: 'translateY(100%)', opacity: 1 }],
          { duration: rm ? 250 : seconds * 800, easing: 'cubic-bezier(0.65,0,0.35,1)', fill: 'forwards' },
        )
        .finished.then(() => {
          f.getAnimations().forEach((a) => a.cancel());
          f.style.opacity = '0';
        });
    }
    if (f) f.style.opacity = '0';
    this.state.in = 1;
    this.state.out = 0;
    return this.tween('out', 1, seconds).then(() => {
      this.state = { in: 0, out: 0 };
      this.render();
    });
  }

  private async showLabel(text: string, color: RGB) {
    const l = this.label;
    if (!l || !text) return;
    l.textContent = text;
    l.style.color = luminance(color) < 0.5 ? 'hsl(38 22% 88%)' : 'hsl(40 5% 11%)';
    await l.animate(
      [
        { transform: 'translateY(40%)', opacity: 0 },
        { transform: 'translateY(0)', opacity: 1 },
      ],
      { duration: reducedMotion() ? 1 : 520, easing: 'cubic-bezier(0.19,1,0.22,1)', fill: 'forwards' },
    ).finished;
  }

  private async hideLabel() {
    const l = this.label;
    if (!l || !l.textContent) return;
    await l.animate(
      [
        { transform: 'translateY(0)', opacity: 1 },
        { transform: 'translateY(-50%)', opacity: 0 },
      ],
      { duration: reducedMotion() ? 1 : 380, easing: 'cubic-bezier(0.4,0,1,1)', fill: 'forwards' },
    ).finished;
    l.textContent = '';
  }

  /**
   * Tear a sheet across the app, name what is happening on it, do the work
   * underneath, and tear it away again. Ignored while one is already running.
   */
  async turn(opts: {
    color: RGB | (() => RGB);
    label?: string;
    /** The work done while the screen is covered. */
    during: () => void;
    /** Called as the sheet starts to tear away. */
    onReveal?: () => void;
    hold?: number;
  }) {
    if (this.busy) return;
    this.busy = true;
    try {
      const color = typeof opts.color === 'function' ? opts.color() : opts.color;
      await this.cover(color);
      await this.showLabel(opts.label ?? '', color);
      opts.during();
      // One frame for React to lay the new page out, then a beat to read the label.
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      await wait(reducedMotion() ? 0 : (opts.hold ?? 260));
      await this.hideLabel();
      const revealed = this.reveal(1.05);
      opts.onReveal?.();
      await revealed;
    } finally {
      this.busy = false;
    }
  }
}

export const curtain = new Curtain();
