/**
 * graph-renderer.js — Canvas force-directed graph for knowledge graph visualization
 * No external dependencies. ~200 lines.
 */
(function (global) {
  const COLORS = ["#007aff","#34c759","#ff9500","#ff3b30","#af52de","#5ac8fa","#ffcc00","#ff6b35"];
  const REL_COLORS = {
    extends: "#007aff",
    related: "#34c759",
    prerequisite: "#ff9500",
    contradicts: "#ff3b30",
  };
  const REL_DASH = {
    extends: [],
    related: [4, 4],
    prerequisite: [8, 3],
    contradicts: [2, 4],
  };

  function GraphRenderer(canvas, graphData, entryMap, onNodeClick) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.graphData = graphData;
    this.entryMap = entryMap;
    this.onNodeClick = onNodeClick;
    this.nodes = [];
    this.edges = [];
    this.dragging = null;
    this.dragOffX = 0;
    this.dragOffY = 0;
    this.hoveredNode = null;
    this.animFrame = null;
    this._build();
    this._bindEvents();
    this._startSim();
  }

  GraphRenderer.prototype._build = function () {
    const clusters = this.graphData.clusters || [];
    const rels = this.graphData.relationships || [];
    const w = this.canvas.width, h = this.canvas.height;

    // Create nodes
    const nodeMap = {};
    clusters.forEach((c, ci) => {
      (c.entry_ids || []).forEach((id) => {
        if (nodeMap[id]) return;
        const entry = this.entryMap[id];
        const node = {
          id,
          label: entry ? entry.title : id,
          color: COLORS[ci % COLORS.length],
          x: w / 2 + (Math.random() - 0.5) * w * 0.6,
          y: h / 2 + (Math.random() - 0.5) * h * 0.6,
          vx: 0, vy: 0,
          r: 10,
        };
        nodeMap[id] = node;
        this.nodes.push(node);
      });
    });

    // Create edges
    rels.forEach((r) => {
      if (nodeMap[r.from_id] && nodeMap[r.to_id]) {
        this.edges.push({
          from: nodeMap[r.from_id],
          to: nodeMap[r.to_id],
          relation: r.relation || "related",
        });
      }
    });
  };

  GraphRenderer.prototype._tick = function () {
    const nodes = this.nodes;
    const edges = this.edges;
    const w = this.canvas.width, h = this.canvas.height;
    const cx = w / 2, cy = h / 2;

    // Repulsion between nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = 3000 / (dist * dist);
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }

    // Spring attraction along edges
    edges.forEach((e) => {
      const dx = e.to.x - e.from.x, dy = e.to.y - e.from.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const target = 120;
      const force = (dist - target) * 0.04;
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      e.from.vx += fx; e.from.vy += fy;
      e.to.vx -= fx; e.to.vy -= fy;
    });

    // Center gravity
    nodes.forEach((n) => {
      n.vx += (cx - n.x) * 0.003;
      n.vy += (cy - n.y) * 0.003;
    });

    // Integrate + damping
    nodes.forEach((n) => {
      if (n === this.dragging) return;
      n.vx *= 0.85; n.vy *= 0.85;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(n.r + 2, Math.min(w - n.r - 2, n.x));
      n.y = Math.max(n.r + 2, Math.min(h - n.r - 2, n.y));
    });
  };

  GraphRenderer.prototype._draw = function () {
    const ctx = this.ctx;
    const w = this.canvas.width, h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Draw edges
    this.edges.forEach((e) => {
      const color = REL_COLORS[e.relation] || "#aaa";
      const dash = REL_DASH[e.relation] || [];
      ctx.beginPath();
      ctx.setLineDash(dash);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.6;
      ctx.moveTo(e.from.x, e.from.y);
      ctx.lineTo(e.to.x, e.to.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    });

    // Draw nodes
    this.nodes.forEach((n) => {
      const isHovered = n === this.hoveredNode;
      ctx.beginPath();
      ctx.arc(n.x, n.y, isHovered ? n.r + 3 : n.r, 0, Math.PI * 2);
      ctx.fillStyle = n.color;
      ctx.globalAlpha = isHovered ? 1 : 0.85;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isHovered) {
        // Tooltip
        const label = n.label.length > 30 ? n.label.slice(0, 30) + "…" : n.label;
        const padding = 6;
        ctx.font = "12px -apple-system, sans-serif";
        const tw = ctx.measureText(label).width;
        let tx = n.x + n.r + 6;
        let ty = n.y - 8;
        if (tx + tw + padding * 2 > w) tx = n.x - tw - padding * 2 - n.r - 6;
        ctx.fillStyle = "rgba(0,0,0,0.75)";
        ctx.beginPath();
        ctx.roundRect(tx, ty, tw + padding * 2, 22, 4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.fillText(label, tx + padding, ty + 15);
      }
    });
  };

  GraphRenderer.prototype._loop = function () {
    this._tick();
    this._draw();
    this.animFrame = requestAnimationFrame(this._loop.bind(this));
  };

  GraphRenderer.prototype._startSim = function () {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
    this._loop();
  };

  GraphRenderer.prototype.destroy = function () {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
  };

  GraphRenderer.prototype._nodeAt = function (x, y) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      const dx = x - n.x, dy = y - n.y;
      if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
    }
    return null;
  };

  GraphRenderer.prototype._bindEvents = function () {
    const canvas = this.canvas;
    const self = this;

    function pos(e) {
      const rect = canvas.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      return { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
    }

    canvas.addEventListener("mousedown", function (e) {
      const p = pos(e);
      const n = self._nodeAt(p.x, p.y);
      if (n) { self.dragging = n; self.dragOffX = p.x - n.x; self.dragOffY = p.y - n.y; }
    });

    canvas.addEventListener("mousemove", function (e) {
      const p = pos(e);
      if (self.dragging) {
        self.dragging.x = p.x - self.dragOffX;
        self.dragging.y = p.y - self.dragOffY;
        self.dragging.vx = 0; self.dragging.vy = 0;
      } else {
        self.hoveredNode = self._nodeAt(p.x, p.y);
        canvas.style.cursor = self.hoveredNode ? "pointer" : "default";
      }
    });

    canvas.addEventListener("mouseup", function (e) {
      const p = pos(e);
      if (self.dragging) {
        const moved = Math.abs(p.x - (self.dragging.x + self.dragOffX)) < 5 &&
                      Math.abs(p.y - (self.dragging.y + self.dragOffY)) < 5;
        if (moved && self.onNodeClick) self.onNodeClick(self.dragging.id);
        self.dragging = null;
      }
    });

    canvas.addEventListener("mouseleave", function () {
      self.dragging = null;
      self.hoveredNode = null;
      canvas.style.cursor = "default";
    });

    // Touch support
    canvas.addEventListener("touchstart", function (e) {
      e.preventDefault();
      const p = pos(e);
      const n = self._nodeAt(p.x, p.y);
      if (n) { self.dragging = n; self.dragOffX = p.x - n.x; self.dragOffY = p.y - n.y; }
    }, { passive: false });

    canvas.addEventListener("touchmove", function (e) {
      e.preventDefault();
      const p = pos(e);
      if (self.dragging) {
        self.dragging.x = p.x - self.dragOffX;
        self.dragging.y = p.y - self.dragOffY;
        self.dragging.vx = 0; self.dragging.vy = 0;
      }
    }, { passive: false });

    canvas.addEventListener("touchend", function (e) {
      self.dragging = null;
    });
  };

  global.GraphRenderer = GraphRenderer;
})(window);
