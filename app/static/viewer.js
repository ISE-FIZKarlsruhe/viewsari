(function () {
  var raw      = JSON.parse(document.getElementById("vsr-data").textContent);
  var SEGS     = raw.segs;
  var SPEECHES = raw.speeches;
  var QIDS     = raw.qids;
  var MENTIONS = raw.mentions;
  var WD       = raw.wd;
  var PARA     = raw.para;
  var BIBLIO   = raw.biblio || {};
  var FAC_PAGES    = raw.all_pages || [];   // all pages for this biography
  var FAC_CUR      = raw.pages     || [];   // pages for the current paragraph
  var FAC_VOL      = raw.vol       || "";
  var PAGE_MAP     = raw.page_map  || {};   // page_number → paragraph_id
  var OCR_HL       = raw.ocr_hl    || {};   // page → { img_w, img_h, rects }

  document.getElementById("vasari-img").src = raw.vasari;

  // ── Wikidata image cache & fetcher ────────────────────────────────
  var wdImageCache = {};  // qid → url or null

  function fetchWdImage(qid, callback) {
    if (qid in wdImageCache) { callback(wdImageCache[qid]); return; }
    var url = "https://www.wikidata.org/w/api.php?action=wbgetclaims&entity=" +
              qid + "&property=P18&format=json&origin=*";
    fetch(url).then(function(r) { return r.json(); }).then(function(data) {
      var claims = data.claims && data.claims.P18;
      if (claims && claims.length) {
        var filename = claims[0].mainsnak.datavalue.value;
        var imgUrl = "https://commons.wikimedia.org/wiki/Special:FilePath/" +
                     encodeURIComponent(filename) + "?width=400";
        wdImageCache[qid] = imgUrl;
        callback(imgUrl);
      } else {
        wdImageCache[qid] = null;
        callback(null);
      }
    }).catch(function() { wdImageCache[qid] = null; callback(null); });
  }

  // ── Facsimile booklet ─────────────────────────────────────────────
  var facIdx = 0;  // index into FAC_PAGES
  var facCurrentPage = 0;  // page number currently displayed
  var facOverlay = document.getElementById("fac-overlay");
  var facRects = [];  // {el, mid} — one per OCR-matched mention on current page
  var pendingHighlight = null;  // mention ID to highlight after page switch

  function facUrl(pageNum) {
    return "/facsimile/" + FAC_VOL + "/" + pageNum + ".png";
  }

  function facShow(idx, navigate) {
    if (!FAC_PAGES.length) return;
    facIdx = Math.max(0, Math.min(idx, FAC_PAGES.length - 1));
    var page = FAC_PAGES[facIdx];

    // If this page belongs to a different paragraph, navigate there
    if (navigate !== false) {
      var targetPara = PAGE_MAP[String(page)];
      if (targetPara && targetPara !== PARA.paragraph_id) {
        // Extract slug from URL: /biography/{slug}/{para_id}
        var pathParts = window.location.pathname.split("/");
        var slug = pathParts[2] || "";
        window.location.href = "/biography/" + slug + "/" + targetPara + "?page=" + page;
        return;
      }
    }

    var img = document.getElementById("fac-img");
    img.src = facUrl(page);
    img.style.display = "block";
    document.getElementById("fac-placeholder").style.display = "none";
    document.getElementById("fac-cur-page").textContent = page;
    document.getElementById("fac-page-pos").textContent = (facIdx + 1) + "/" + FAC_PAGES.length;
    document.getElementById("fac-prev").disabled = (facIdx === 0);
    document.getElementById("fac-next").disabled = (facIdx === FAC_PAGES.length - 1);
    // Update thumbnail highlights
    document.querySelectorAll(".fac-thumb").forEach(function(t) {
      t.classList.toggle("active", parseInt(t.dataset.page) === page);
    });
    // Store current page for overlay rebuild after image loads
    facCurrentPage = page;
  }

  function facInit() {
    if (!FAC_PAGES.length || !FAC_VOL) return;
    document.getElementById("fac-controls").style.display = "flex";
    document.getElementById("fac-thumbs").style.display = "flex";
    document.getElementById("fac-prev").addEventListener("click", function() { facShow(facIdx - 1, true); });
    document.getElementById("fac-next").addEventListener("click", function() { facShow(facIdx + 1, true); });

    // Build thumbnail strip
    var strip = document.getElementById("fac-thumbs");
    strip.innerHTML = "";
    FAC_PAGES.forEach(function(page, i) {
      var div = document.createElement("div");
      div.className = "fac-thumb";
      div.dataset.page = page;
      // Mark pages belonging to current paragraph
      if (FAC_CUR.indexOf(page) !== -1) {
        div.classList.add("current-para");
      }
      var img = document.createElement("img");
      img.src = facUrl(page);
      img.alt = "p." + page;
      img.loading = "lazy";
      div.appendChild(img);
      var lbl = document.createElement("div");
      lbl.className = "fac-thumb-label";
      lbl.textContent = page;
      div.appendChild(lbl);
      div.addEventListener("click", function() { facShow(i, true); });
      strip.appendChild(div);
    });

    // Start on the requested page (?page= param), current paragraph's page, or first page
    var startIdx = 0;
    var urlPage = new URLSearchParams(window.location.search).get("page");
    if (urlPage) {
      var pi = FAC_PAGES.indexOf(parseInt(urlPage));
      if (pi !== -1) startIdx = pi;
    } else if (FAC_CUR.length) {
      var ci = FAC_PAGES.indexOf(FAC_CUR[0]);
      if (ci !== -1) startIdx = ci;
    }
    facShow(startIdx, false);  // false = don't navigate on initial load

    // Scroll the active thumb into view
    setTimeout(function() {
      var active = strip.querySelector(".fac-thumb.active");
      if (active) active.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }, 100);
  }

  facInit();

  // ── Facsimile zoom & pan ────────────────────────────────────────────
  (function initFacZoom() {
    var main  = document.getElementById("fac-main");
    var inner = document.getElementById("fac-inner");
    var img   = document.getElementById("fac-img");
    var controls = document.getElementById("fac-zoom-controls");
    if (!main || !inner || !img) return;

    var scale = 1;
    var baseW = 0, baseH = 0;   // image size at scale=1, fit to container
    var ox = 0, oy = 0;         // origin offset (centring at scale=1)
    var tx = 0, ty = 0;         // user pan offset (pixels, at scale=1)
    var MIN_SCALE = 1, MAX_SCALE = 6;
    var dragging = false, lastX = 0, lastY = 0;

    function fitImage() {
      // Compute the image size that fits the container while preserving aspect ratio
      var mw = main.clientWidth, mh = main.clientHeight;
      var natW = img.naturalWidth, natH = img.naturalHeight;
      if (!natW || !natH) return;
      var ratio = Math.min(mw / natW, mh / natH);
      baseW = natW * ratio;
      baseH = natH * ratio;
      img.style.width = baseW + "px";
      img.style.height = baseH + "px";
      // Centre in container
      ox = (mw - baseW) / 2;
      oy = (mh - baseH) / 2;
    }

    function apply() {
      var x = ox + tx * scale;
      var y = oy + ty * scale;
      inner.style.transform = "translate(" + x + "px," + y + "px) scale(" + scale + ")";
    }

    function clampPan() {
      if (scale <= 1) { tx = 0; ty = 0; return; }
      var mw = main.clientWidth, mh = main.clientHeight;
      var sw = baseW * scale, sh = baseH * scale;
      // Don't let any edge come inside the viewport
      var minTx = (mw - sw - 2 * ox) / scale;
      var maxTx = -ox * (scale - 1) / scale;
      if (minTx > maxTx) { var mid = (minTx + maxTx) / 2; minTx = maxTx = mid; }
      tx = Math.max(minTx, Math.min(maxTx, tx));
      var minTy = (mh - sh - 2 * oy) / scale;
      var maxTy = -oy * (scale - 1) / scale;
      if (minTy > maxTy) { var midY = (minTy + maxTy) / 2; minTy = maxTy = midY; }
      ty = Math.max(minTy, Math.min(maxTy, ty));
    }

    function zoomTo(newScale, cx, cy) {
      var mw = main.clientWidth, mh = main.clientHeight;
      if (cx == null) cx = mw / 2;
      if (cy == null) cy = mh / 2;
      newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale));
      // Adjust pan so the point under (cx, cy) stays fixed
      // Current world coords under cursor: wx = (cx - ox) / scale - tx, same for y
      var wx = (cx - ox) / scale - tx;
      var wy = (cy - oy) / scale - ty;
      scale = newScale;
      tx = (cx - ox) / scale - wx;
      ty = (cy - oy) / scale - wy;
      clampPan();
      apply();
    }

    function resetZoom() {
      fitImage();
      scale = 1; tx = 0; ty = 0;
      apply();
    }

    // Scroll-wheel zoom
    main.addEventListener("wheel", function(e) {
      if (img.style.display === "none") return;
      e.preventDefault();
      var rect = main.getBoundingClientRect();
      var cx = e.clientX - rect.left;
      var cy = e.clientY - rect.top;
      var delta = e.deltaY > 0 ? -0.15 : 0.15;
      zoomTo(scale * (1 + delta), cx, cy);
    }, { passive: false });

    // Drag to pan
    main.addEventListener("mousedown", function(e) {
      if (img.style.display === "none") return;
      if (e.button !== 0) return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      main.classList.add("dragging");
      e.preventDefault();
    });
    window.addEventListener("mousemove", function(e) {
      if (!dragging) return;
      tx += (e.clientX - lastX) / scale;
      ty += (e.clientY - lastY) / scale;
      lastX = e.clientX;
      lastY = e.clientY;
      clampPan();
      apply();
    });
    window.addEventListener("mouseup", function() {
      if (dragging) { dragging = false; main.classList.remove("dragging"); }
    });

    // Touch: pinch-zoom + drag
    var touches0 = null, touchDist0 = 0, touchScale0 = 1;
    main.addEventListener("touchstart", function(e) {
      if (img.style.display === "none") return;
      if (e.touches.length === 2) {
        e.preventDefault();
        touches0 = [e.touches[0], e.touches[1]];
        touchDist0 = Math.hypot(touches0[1].clientX - touches0[0].clientX, touches0[1].clientY - touches0[0].clientY);
        touchScale0 = scale;
      } else if (e.touches.length === 1) {
        dragging = true;
        lastX = e.touches[0].clientX;
        lastY = e.touches[0].clientY;
      }
    }, { passive: false });
    main.addEventListener("touchmove", function(e) {
      if (img.style.display === "none") return;
      if (e.touches.length === 2 && touches0) {
        e.preventDefault();
        var dist = Math.hypot(e.touches[1].clientX - e.touches[0].clientX, e.touches[1].clientY - e.touches[0].clientY);
        var rect = main.getBoundingClientRect();
        var cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
        var cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
        zoomTo(touchScale0 * (dist / touchDist0), cx, cy);
      } else if (dragging && e.touches.length === 1) {
        tx += (e.touches[0].clientX - lastX) / scale;
        ty += (e.touches[0].clientY - lastY) / scale;
        lastX = e.touches[0].clientX;
        lastY = e.touches[0].clientY;
        clampPan();
        apply();
      }
    }, { passive: false });
    main.addEventListener("touchend", function() {
      dragging = false; touches0 = null;
    });

    // Double-click to zoom in at point
    main.addEventListener("dblclick", function(e) {
      if (img.style.display === "none") return;
      var rect = main.getBoundingClientRect();
      var cx = e.clientX - rect.left;
      var cy = e.clientY - rect.top;
      if (scale > 1.5) { resetZoom(); }
      else { zoomTo(3, cx, cy); }
    });

    // Button controls
    document.getElementById("fac-zoom-in").addEventListener("click", function() { zoomTo(scale * 1.4); });
    document.getElementById("fac-zoom-out").addEventListener("click", function() { zoomTo(scale / 1.4); });
    document.getElementById("fac-zoom-reset").addEventListener("click", resetZoom);

    // Size image and show controls on load; reset on page change
    img.addEventListener("load", function() {
      controls.style.display = "flex";
      resetZoom();
      // Build OCR overlay once image has dimensions
      buildFacOverlay(facCurrentPage);
      // Apply any pending highlight from a page switch
      if (pendingHighlight) {
        var mid = pendingHighlight;
        pendingHighlight = null;
        highlightFacMention(mid);
      }
    });
    window.addEventListener("resize", function() {
      if (img.style.display !== "none") resetZoom();
    });
  })();

  var SVG_NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var el = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs).forEach(function(k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  // ── Graph colour config ──────────────────────────────────────────────
  var GC = {
    biblio:  { s:"#7C3AED", f:"#F5F3FF", t:"#6D28D9", tag:"BIBLIO"  },
    content: { s:"#B45309", f:"#FFFBEB", t:"#92400E", tag:"CONTENT" },
    annot:   { s:"#0F766E", f:"#F0FDF9", t:"#115E59", tag:"ANNOT"   },
    entity:  { s:"#BE185D", f:"#FDF2F8", t:"#9D174D", tag:"ENTITY"  },
    ookb:    { s:"#B91C1C", f:"#FEF2F2", t:"#991B1B", tag:"OOKB"    },
    agent:   { s:"#1D4ED8", f:"#EFF6FF", t:"#1E40AF", tag:"AGENT"   },
  };

  // ── Build focused subgraph for one mention ───────────────────────────
  var graphExpanded = false;  // track whether biblio chain is expanded

  function buildMentionGraph(mentionId) {
    graphExpanded = false;
    var m   = MENTIONS[mentionId];
    var qid = QIDS[mentionId] || null;
    var wd  = (qid && WD[qid]) ? WD[qid] : null;
    var isOokb = m ? !!m.ookb : false;
    var entityLayer = isOokb ? "ookb" : "entity";

    // 7 fixed nodes arranged in a clear left→right flow
    var nodes = [];
    var edges = [];

    // 1. Paragraph (content)
    nodes.push({ id:"para", layer:"content",
      label:"viewsari:para_" + (PARA.paragraph_id || "?"),
      sub:"doco:Paragraph \u00b7 p.\u00a0" + (PARA.page || "?"),
      expandable: true,
      x:20, y:80, w:175, h:54 });

    // 2. TextChunk (content)
    var surface = m ? (m.surface || "").substring(0,36) + (m.surface && m.surface.length>36?"...":"") : "";
    nodes.push({ id:"chunk", layer:"content",
      label:"doco:TextChunk",
      sub:"\u201c" + surface + "\u201d",
      x:230, y:30, w:175, h:54 });

    // 3. Position selector (content)
    nodes.push({ id:"selector", layer:"content",
      label:"oa:TextPositionSelector",
      sub:"oa:start " + (m ? m.start : "?") + " \u00b7 oa:end " + (m ? m.end : "?"),
      x:230, y:120, w:175, h:48 });

    // 4. ObliquER extraction run (annot)
    nodes.push({ id:"run", layer:"annot",
      label:"viewsari:obliquer_run_1",
      sub:"prov:Activity \u00b7 RelationExtraction",
      x:440, y:10, w:185, h:54 });

    // 5. Mention annotation (annot or ookb)
    var typeShort = m ? m.type : "mention";
    nodes.push({ id:"mention", layer: isOokb ? "ookb" : "annot",
      label:"viewsari:" + mentionId,
      sub:typeShort,
      mentionId: mentionId,
      x:440, y:100, w:185, h:54 });

    // 6. Entity linking run (annot)
    nodes.push({ id:"linker", layer:"annot",
      label:"viewsari:entity_linking_run_1",
      sub:"prov:Activity",
      x:660, y:30, w:185, h:48 });

    // 7. Entity / OOKB node (entity or ookb)
    var entitySub = isOokb
      ? "OOKB \u2014 no canonical URI"
      : (qid ? "rdfs:sameAs wd:" + qid : "prov:Entity");
    nodes.push({ id:"entity", layer:entityLayer,
      label: m ? "viewsari:" + m.entity_id : "entity",
      sub: entitySub,
      x:660, y:120, w:185, h:54,
      qid: qid,
      ookb: isOokb,
      wd: wd,
      mentionId: mentionId });

    // Edges
    edges.push({ from:"para",    to:"chunk",   label:"doco:hasTextChunk" });
    edges.push({ from:"chunk",   to:"selector",label:"oa:hasSelector" });
    edges.push({ from:"run",     to:"mention", label:"prov:wasGeneratedBy", dashed:true });
    edges.push({ from:"mention", to:"chunk",   label:"oa:hasTarget" });
    edges.push({ from:"mention", to:"entity",  label:"oa:hasBody" });
    edges.push({ from:"linker",  to:"entity",  label:"prov:wasGeneratedBy", dashed:true });
    if (qid) {
      edges.push({ from:"entity", to:"entity", label:"rdfs:sameAs wd:"+qid, selfloop:true, external:true });
    }

    _lastMentionId = mentionId;
    _lastWd = wd;
    _lastIsOokb = isOokb;
    _lastQid = qid;
    renderGraph(nodes, edges, mentionId, wd, isOokb, qid);
  }

  var _lastMentionId, _lastWd, _lastIsOokb, _lastQid;

  // ── Expand paragraph node with bibliographic chain ──────────────────
  function expandBiblioChain() {
    if (graphExpanded || !BIBLIO.para_uri) return;
    graphExpanded = true;

    // Shift existing nodes right to make room for biblio nodes on the left
    var shiftX = 220;
    gNodes.forEach(function(n) { n.x += shiftX; });

    // Biblio nodes stacked to the left of the paragraph
    var bPage = { id:"b_page", layer:"biblio",
      label: BIBLIO.page_uri ? shortenUri(BIBLIO.page_uri) : BIBLIO.page_label,
      sub: BIBLIO.page_label,
      x: 20, y: 20, w: 185, h: 48 };

    var bBio = { id:"b_bio", layer:"biblio",
      label: BIBLIO.bio_uri ? shortenUri(BIBLIO.bio_uri) : "Biography",
      sub: (BIBLIO.bio_label || "").substring(0, 50),
      x: 20, y: 80, w: 185, h: 48 };

    var bVol = { id:"b_vol", layer:"biblio",
      label: BIBLIO.vol_uri ? shortenUri(BIBLIO.vol_uri) : "Volume",
      sub: (BIBLIO.vol_label || "").substring(0, 50),
      x: 20, y: 140, w: 185, h: 48 };

    var bEd = { id:"b_edition", layer:"biblio",
      label: BIBLIO.edition_uri ? shortenUri(BIBLIO.edition_uri) : "Edition",
      sub: BIBLIO.edition_label || "Le Vite (1568 ed.)",
      x: 20, y: 200, w: 185, h: 48 };

    gNodes.push(bPage, bBio, bVol, bEd);

    // Edges: paragraph → page, page → bio, bio → vol, vol → edition
    gEdges.push({ from:"para", to:"b_page", label:"dct:isPartOf" });
    gEdges.push({ from:"b_page", to:"b_bio", label:"dct:isPartOf" });
    gEdges.push({ from:"b_bio", to:"b_vol", label:"frbr:isPartOf" });
    gEdges.push({ from:"b_vol", to:"b_edition", label:"frbr:isPartOf" });

    renderGraph(gNodes, gEdges, _lastMentionId, _lastWd, _lastIsOokb, _lastQid);
  }

  function shortenUri(uri) {
    if (!uri) return "";
    // viewsari:the_lives_1568_volume-10_paragraph-175 → just last segment
    var parts = uri.replace(/\/+$/, "").split(/[/#]/);
    var last = parts[parts.length - 1] || uri;
    if (last.length > 30) last = last.substring(0, 28) + "\u2026";
    return "viewsari:" + last;
  }

  // ── Render graph ─────────────────────────────────────────────────────
  var gTransform = { x:30, y:30, scale:1 };
  var gNodes     = [];
  var gEdges     = [];
  var gSelected  = null;
  var gDragging  = false;
  var gDragNode  = null;
  var gDragStart = {};
  var gPanning   = false;
  var gPanStart  = {};

  function renderGraph(nodes, edges, mentionId, wd, isOokb, qid) {
    gNodes = nodes;
    gEdges = edges;
    gSelected = null;

    var svg    = document.getElementById("graph-svg");
    var vp     = document.getElementById("g-viewport");
    var eLayer = document.getElementById("g-edges");
    var nLayer = document.getElementById("g-nodes");
    eLayer.innerHTML = "";
    nLayer.innerHTML = "";

    document.getElementById("graph-empty").style.display = "none";

    // Auto-fit
    var W = svg.getBoundingClientRect().width  || 600;
    var H = svg.getBoundingClientRect().height || 300;
    var maxX = 0, maxY = 0;
    nodes.forEach(function(n){ maxX = Math.max(maxX, n.x+n.w); maxY = Math.max(maxY, n.y+n.h); });
    var pad = 40;
    var sx = (W - pad*2) / (maxX);
    var sy = (H - pad*2) / (maxY + 20);
    var s  = Math.min(sx, sy, 1.1);
    gTransform = { x: pad, y: pad + 20, scale: s };
    applyGTransform();

    // Draw edges
    edges.forEach(function(e) {
      if (e.selfloop || e.external) return;
      drawEdge(e, nodes, eLayer);
    });

    // Draw nodes
    nodes.forEach(function(n) {
      var col = GC[n.layer] || GC.content;
      var g = document.createElementNS(SVG_NS, "g");
      g.setAttribute("class", "gnode");
      g.setAttribute("data-id", n.id);
      if (n.mentionId) { g.setAttribute("data-mention-id", n.mentionId); }
      g.setAttribute("transform", "translate("+n.x+","+n.y+")");

      // Shadow rect
      var shadow = svgEl("rect", { x:2,y:2,width:n.w,height:n.h,rx:6,ry:6,fill:"rgba(0,0,0,.06)" });
      g.appendChild(shadow);

      // Background
      var rect = svgEl("rect", {
        class:"gnode-rect gnode-rect-outer",
        width:n.w, height:n.h, rx:6, ry:6,
        fill:col.f, stroke:col.s, "stroke-width":"1.5",
      });
      g.appendChild(rect);

      // Tag strip at top
      var strip = svgEl("rect", { x:0,y:0,width:n.w,height:16,rx:6,ry:6,fill:col.s,"fill-opacity":".12" });
      g.appendChild(strip);
      var stripB = svgEl("rect", { x:0,y:10,width:n.w,height:6,fill:col.s,"fill-opacity":".12" });
      g.appendChild(stripB);

      var tag = svgEl("text", { x:7, y:11, class:"gnode-tag", fill:col.t });
      tag.textContent = col.tag;
      g.appendChild(tag);

      // Label — fits between tag strip (y=16) and sub label area
      var labelFull = n.label;
      var maxChars = Math.floor(n.w / 7);
      var lbl = svgEl("text", { x:7, y:28, class:"gnode-label", fill:col.t });
      lbl.textContent = labelFull.substring(0, maxChars) + (labelFull.length > maxChars ? "\u2026" : "");
      g.appendChild(lbl);

      // Sub label — single line at bottom of node
      var sub = n.sub || "";
      var subMax = Math.floor(n.w / 6.5);
      var s1 = svgEl("text", { x:7, y:n.h-8, class:"gnode-sub", fill:col.t, "fill-opacity":".7" });
      s1.textContent = sub.substring(0, subMax) + (sub.length > subMax ? "\u2026" : "");
      g.appendChild(s1);

      // Expand indicator for expandable nodes
      if (n.expandable && !graphExpanded) {
        var expHint = svgEl("text", { x:n.w-8, y:11, class:"gnode-tag", fill:col.t, "text-anchor":"end", "font-size":"8" });
        expHint.textContent = "\u21c4 dbl-click";
        g.appendChild(expHint);
      }

      // Interactions
      g.addEventListener("click", function(ev) {
        ev.stopPropagation();
        handleNodeClick(n, col);
      });
      g.addEventListener("dblclick", function(ev) {
        ev.stopPropagation();
        if (n.expandable) {
          expandBiblioChain();
        }
      });
      makeDraggable(g, n);
      nLayer.appendChild(g);
    });

    // Update graph title
    var mention = MENTIONS[mentionId];
    var mtype = mention ? mention.type : "";
    document.getElementById("graph-title").textContent =
      "Provenance graph \u00b7 " + mentionId + " \u00b7 " + mtype;
  }

  function highlightTextMention(mentionId) {
    document.querySelectorAll(".ann.graph-highlight").forEach(function(a){
      a.classList.remove("graph-highlight");
    });
    if (!mentionId) return;

    // Find the entity_id for this mention
    var m = MENTIONS[mentionId];
    var entityId = m ? m.entity_id : null;

    // Collect all mention IDs that share the same entity_id
    var toHighlight = [];
    if (entityId) {
      Object.keys(MENTIONS).forEach(function(mid) {
        if (MENTIONS[mid].entity_id === entityId) { toHighlight.push(mid); }
      });
    } else {
      toHighlight = [mentionId];
    }

    // Highlight all matching spans
    var firstSpan = null;
    toHighlight.forEach(function(mid) {
      var span = document.querySelector(".ann[data-id=\"" + mid + "\"]");
      if (!span) return;
      span.classList.add("lit");
      span.classList.add("graph-highlight");
      if (!firstSpan) firstSpan = span;
    });

    // Scroll to the primary (first/longest) mention
    if (firstSpan) {
      firstSpan.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    setTimeout(function() {
      document.querySelectorAll(".ann.graph-highlight").forEach(function(a){
        a.classList.remove("graph-highlight");
      });
    }, 3800);
  }

  function handleNodeClick(n, col) {
    // Highlight in graph
    gSelected = n.id;
    document.querySelectorAll(".gnode").forEach(function(g){
      g.classList.toggle("selected", g.getAttribute("data-id") === n.id);
    });
    // Highlight in text
    if (n.mentionId) { highlightTextMention(n.mentionId); }

    // Show info in a small overlay inside the graph
    var info = document.getElementById("g-info");
    var html = "<div style='font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:"+col.s+";margin-bottom:4px'>"+col.tag+"</div>";
    html += "<div style='font-size:12px;font-weight:600;color:var(--tp);margin-bottom:6px;word-break:break-all'>"+n.label+"</div>";
    if (n.sub) html += "<div style='font-size:11px;color:var(--ts);margin-bottom:8px'>"+n.sub+"</div>";
    if (n.wd) {
      html += "<div style='font-size:10px;color:var(--tt);margin-bottom:3px;text-transform:uppercase;letter-spacing:.06em;font-weight:700'>Wikidata record</div>";
      if (n.wd.title)    html += "<div style='font-size:12px;font-weight:600;color:var(--tp);margin-bottom:2px'>"+n.wd.title+"</div>";
      if (n.wd.creator)  html += "<div style='font-size:11px;color:var(--ts)'>"+n.wd.creator+" &middot; "+(n.wd.date||"")+"</div>";
      if (n.wd.location) html += "<div style='font-size:11px;color:var(--ts)'>"+n.wd.location+"</div>";
      if (n.wd.depicts)  html += "<div style='font-size:11px;color:var(--ts);margin-top:2px'>"+n.wd.depicts+"</div>";
      if (n.qid)         html += "<a href='https://www.wikidata.org/wiki/"+n.qid+"' target='_blank' style='font-size:11px;color:#1B6EF3;text-decoration:none;margin-top:6px;display:inline-block'>\u2197 wd:"+n.qid+"</a>";
    }
    if (n.ookb) {
      html += "<div style='font-size:11px;color:#B91C1C;background:#FEF2F2;border:1px solid #FCA5A5;border-radius:5px;padding:6px 8px;margin-top:4px'>Out-of-knowledge-base &mdash; no canonical URI</div>";
      var nodeM = n.mentionId ? MENTIONS[n.mentionId] : null;
      var nodeOokbUri = nodeM ? (nodeM.ookb_uri || "") : "";
      if (nodeOokbUri) {
        html += "<a href='" + nodeOokbUri + "' target='_blank' style='font-size:11px;color:#1B6EF3;text-decoration:none;margin-top:6px;display:inline-block'>\u2197 Open in Viewsari KB</a>";
      }
    }
    // WGA link in graph info panel
    var infoM = n.mentionId ? MENTIONS[n.mentionId] : null;
    var infoWga = infoM ? (infoM.wga_id || "") : "";
    if (infoWga) {
      html += "<a href='" + infoWga + "' target='_blank' style='font-size:11px;color:#1B6EF3;text-decoration:none;margin-top:6px;display:inline-block'>\u2197 Web Gallery of Art</a>";
    }
    info.innerHTML = html;
    info.style.display = "block";
  }

  function applyGTransform() {
    var vp = document.getElementById("g-viewport");
    vp.setAttribute("transform",
      "translate("+gTransform.x+","+gTransform.y+") scale("+gTransform.scale+")");
  }

  // Drag nodes
  function makeDraggable(g, n) {
    var dg=false, smx, smy, snx, sny;
    g.addEventListener("mousedown", function(ev) {
      if(ev.button!==0)return;
      dg=true; smx=ev.clientX; smy=ev.clientY; snx=n.x; sny=n.y;
      ev.stopPropagation(); ev.preventDefault();
      document.getElementById("graph-svg").classList.add("dragging");
    });
    window.addEventListener("mousemove", function(ev) {
      if(!dg)return;
      n.x = snx + (ev.clientX-smx)/gTransform.scale;
      n.y = sny + (ev.clientY-smy)/gTransform.scale;
      g.setAttribute("transform","translate("+n.x+","+n.y+")");
      redrawEdges();
    });
    window.addEventListener("mouseup", function() {
      if(dg){ dg=false; document.getElementById("graph-svg").classList.remove("dragging"); }
    });
  }

  function drawEdge(e, nodes, eLayer) {
    var src = nodes.find(function(n){ return n.id === e.from; });
    var tgt = nodes.find(function(n){ return n.id === e.to;   });
    if (!src || !tgt) return;

    // Determine connection points based on relative position
    var x1, y1, x2, y2;
    if (src.x + src.w <= tgt.x) {
      // src is left of tgt: right edge → left edge
      x1 = src.x + src.w; y1 = src.y + src.h/2;
      x2 = tgt.x;         y2 = tgt.y + tgt.h/2;
    } else if (tgt.x + tgt.w <= src.x) {
      // tgt is left of src: left edge → right edge
      x1 = src.x;           y1 = src.y + src.h/2;
      x2 = tgt.x + tgt.w;   y2 = tgt.y + tgt.h/2;
    } else {
      // Overlapping x: connect top/bottom
      x1 = src.x + src.w/2; y1 = src.y + src.h;
      x2 = tgt.x + tgt.w/2; y2 = tgt.y;
    }
    var mx = (x1+x2)/2;

    var path = svgEl("path", {
      d: "M"+x1+","+y1+" C"+mx+","+y1+" "+mx+","+y2+" "+x2+","+y2,
      class: "gedge" + (e.dashed?" gedge-dashed":""),
      stroke: "#D1D5DB",
      "marker-end": "url(#garrow)",
    });
    eLayer.appendChild(path);

    var lx = (x1+x2)/2, ly = (y1+y2)/2 - 5;
    var lt = svgEl("text", { x:lx, y:ly, class:"gedge-label", "text-anchor":"middle" });
    lt.textContent = e.label;
    eLayer.appendChild(lt);
  }

  function redrawEdges() {
    var eLayer = document.getElementById("g-edges");
    eLayer.innerHTML = "";
    gEdges.forEach(function(e) {
      if (e.selfloop||e.external) return;
      drawEdge(e, gNodes, eLayer);
    });
  }

  // Pan graph
  var gsvg = document.getElementById("graph-svg");
  gsvg.addEventListener("mousedown", function(ev) {
    if(ev.target.closest(".gnode")) return;
    gPanning=true;
    gPanStart={x:ev.clientX-gTransform.x, y:ev.clientY-gTransform.y};
    ev.preventDefault();
  });
  window.addEventListener("mousemove", function(ev) {
    if(!gPanning) return;
    gTransform.x = ev.clientX - gPanStart.x;
    gTransform.y = ev.clientY - gPanStart.y;
    applyGTransform();
  });
  window.addEventListener("mouseup", function(){ gPanning=false; });
  gsvg.addEventListener("wheel", function(ev) {
    ev.preventDefault();
    var f=ev.deltaY<0?1.1:0.9;
    var r=gsvg.getBoundingClientRect();
    var mx=ev.clientX-r.left, my=ev.clientY-r.top;
    gTransform.x=mx-(mx-gTransform.x)*f;
    gTransform.y=my-(my-gTransform.y)*f;
    gTransform.scale=Math.min(Math.max(gTransform.scale*f,.15),3);
    applyGTransform();
  },{passive:false});
  gsvg.addEventListener("click", function(ev) {
    if(!ev.target.closest(".gnode")) {
      gSelected=null;
      document.querySelectorAll(".gnode").forEach(function(g){g.classList.remove("selected");});
      document.getElementById("g-info").style.display="none";
    }
  });

  function resetGraphZoom() {
    if(!gNodes.length) return;
    var W=gsvg.getBoundingClientRect().width||600;
    var H=gsvg.getBoundingClientRect().height||300;
    var maxX=0,maxY=0;
    gNodes.forEach(function(n){maxX=Math.max(maxX,n.x+n.w);maxY=Math.max(maxY,n.y+n.h);});
    var s=Math.min((W-80)/maxX,(H-80)/maxY,1.1);
    gTransform={x:40,y:40,scale:s};
    applyGTransform();
  }

  // ── Text builder ────────────────────────────────────────────────────
  function esc(s) { var d=document.createElement("div");d.textContent=s;return d.innerHTML; }

  function buildText() {
    var h="";
    for(var i=0;i<SEGS.length;i++) {
      var s=SEGS[i];
      if(!s.y){h+=esc(s.t);continue;}
      var hasDet=!!(SPEECHES[s.id]||QIDS[s.id]);
      var ookb=s.o?"<sup class=\"ookb\">OOKB</sup>":"";
      var dot=hasDet?"<span class=\"ann-dot\"></span>":"";
      var badge=s.y==="explicit"?"E":s.y==="implicit"?"I":s.y==="coref"?"\u21ba":"G";
      h+="<span class=\"ann "+s.y+"\" data-id=\""+s.id+"\" onclick=\"VSR.open(this)\">"+esc(s.t)+ookb+dot+"<span class=\"badge\">"+badge+"</span></span>";
    }
    document.getElementById("tbody").innerHTML=h;
  }

  // ── Scanner ─────────────────────────────────────────────────────────
  var scanTimer=null;
  function startScan() {
    doClear();
    var anns=document.querySelectorAll(".ann");
    var fb=document.getElementById("fb"),tb=document.getElementById("tb"),st=document.getElementById("st");
    var totalH=document.querySelector(".textbody").offsetHeight;
    var i=0;
    fb.classList.add("on");tb.classList.add("on");
    document.getElementById("bscan").classList.add("active");
    function step(){
      if(i>=anns.length){
        fb.classList.remove("on");tb.classList.remove("on");
        document.getElementById("bscan").classList.remove("active");
        st.textContent=anns.length+" mentions \u2014 click any underlined term";
        return;
      }
      anns[i].classList.add("lit");
      var r=anns[i].getBoundingClientRect();
      var base=document.querySelector(".textbody").getBoundingClientRect();
      var rel=(r.top-base.top+r.height/2)/totalH;
      tb.style.top=(rel*totalH)+"px";fb.style.top=(rel*totalH)+"px";
      st.textContent=(i+1)+" / "+anns.length;
      i++;scanTimer=setTimeout(step,75);
    }
    step();
  }

  function revealAll(){
    clearTimeout(scanTimer);
    document.querySelectorAll(".ann").forEach(function(a){a.classList.add("lit");});
    document.getElementById("fb").classList.remove("on");
    document.getElementById("tb").classList.remove("on");
    document.getElementById("bscan").classList.remove("active");
    document.getElementById("st").textContent="All annotations visible \u2014 click any underlined term";
  }

  // ── Typewriter ───────────────────────────────────────────────────────
  var typeTimer=null;
  function typeWrite(el,text){
    clearTimeout(typeTimer);
    el.textContent="";el.classList.add("typing-cursor");
    var i=0;
    function tick(){
      if(i<text.length){el.textContent+=text.charAt(i++);typeTimer=setTimeout(tick,16);}
      else{el.classList.remove("typing-cursor");}
    }
    tick();
  }

  // ── Open detail ──────────────────────────────────────────────────────
  function openDetail(el) {
    var id=el.getAttribute("data-id");
    document.querySelectorAll(".ann.pick").forEach(function(a){a.classList.remove("pick");});
    el.classList.add("pick");el.classList.add("lit");
    highlightFacMention(id);

    var det=document.getElementById("detail");
    det.classList.add("open");
    setTimeout(function(){det.scrollIntoView({behavior:"smooth",block:"end"});},120);

    // Vasari rises
    var vw=document.getElementById("vasari-wrap");
    vw.classList.remove("risen");void vw.offsetWidth;
    setTimeout(function(){vw.classList.add("risen");},100);

    // Speech
    var isOokb=!!(el.querySelector(".ookb"));
    var speech=isOokb
      ?"This entity has not yet been traced to a canonical identifier \u2014 it exists in Vasari\u2019s text but lies outside the knowledge base. Help make this a traceable entity!"
      :(SPEECHES[id]||"I have little to say of this mention specifically \u2014 though every word of The Lives was weighed carefully.");
    var bubble=document.getElementById("bubble");
    bubble.textContent="";bubble.classList.add("typing-cursor");
    setTimeout(function(){typeWrite(bubble,speech);},450);

    // Artwork + WD panel
    var qid  = QIDS[id];
    var artI = document.getElementById("art-img");
    var wdP  = document.getElementById("wd-panel");
    artI.classList.remove("risen");
    artI.src = "";
    artI.style.display = "none";
    wdP.innerHTML = "";

    var mention = MENTIONS[id];
    var ookbUri = mention ? (mention.ookb_uri || "") : "";
    var wdId = mention ? (mention.wikidata_id || "") : "";
    var wgaId = mention ? (mention.wga_id || "") : "";
    var effectiveQid = qid || (wdId ? wdId.replace(/.*\//, "") : "");

    // Helper: show artwork image (prefer WGA, fallback to Wikidata P18)
    function showArtImage(q) {
      if (wgaId) {
        var wgaImgUrl = wgaId.replace("/html_m/", "/detail_s/").replace(/\.html$/, ".jpg");
        artI.src = wgaImgUrl;
        artI.style.display = "block";
        artI.classList.remove("risen");
        void artI.offsetWidth;
        setTimeout(function() { artI.classList.add("risen"); }, 80);
        return;
      }
      if (!q || !q.startsWith("Q")) return;
      fetchWdImage(q, function(imgUrl) {
        if (imgUrl) {
          artI.src = imgUrl;
          artI.style.display = "block";
          artI.classList.remove("risen");
          void artI.offsetWidth;
          setTimeout(function() { artI.classList.add("risen"); }, 80);
        }
      });
    }

    // Helper: WGA link HTML
    function wgaLinkHtml() {
      if (!wgaId) return "";
      return "<a class=\"wd-link\" href=\"" + esc(wgaId) + "\" target=\"_blank\" style=\"margin-top:4px;display:inline-block\">\u2197 Web Gallery of Art</a>";
    }

    if (isOokb) {
      var ookbHtml = "<div class=\"wd-ookb\">\u26a0 Out-of-knowledge-base \u2014 no canonical identifier.</div>";
      if (ookbUri) {
        ookbHtml += "<a class=\"wd-link\" href=\"" + esc(ookbUri) + "\" target=\"_blank\" style=\"margin-top:8px;display:inline-block\">\u2197 Open in Viewsari KB</a>";
      }
      ookbHtml += wgaLinkHtml();
      wdP.innerHTML = ookbHtml;
      if (wgaId) showArtImage(null);
    } else if (qid && WD[qid]) {
      var rec = WD[qid];
      var dlRows = "";
      if (rec.location) dlRows += "<dt>Location</dt><dd>" + esc(rec.location) + "</dd>";
      if (rec.material)  dlRows += "<dt>Material</dt><dd>" + esc(rec.material) + "</dd>";
      if (rec.depicts)   dlRows += "<dt>Depicts</dt><dd>"  + esc(rec.depicts)  + "</dd>";
      wdP.innerHTML =
        "<div class=\"wd-qid\">wd:" + qid + "</div>" +
        "<div class=\"wd-title\">" + esc(rec.title) + "</div>" +
        (rec.creator ? "<div class=\"wd-creator\">" + esc(rec.creator) + (rec.date ? " \u00b7 " + esc(rec.date) : "") + "</div>" : "") +
        (dlRows ? "<dl class=\"wd-dl\">" + dlRows + "</dl>" : "") +
        "<a class=\"wd-link\" href=\"https://www.wikidata.org/wiki/" + qid + "\" target=\"_blank\">\u2197 Wikidata</a>" +
        wgaLinkHtml();
      showArtImage(qid);
    } else if (effectiveQid && effectiveQid.startsWith("Q")) {
      wdP.innerHTML =
        "<div class=\"wd-qid\">wd:" + effectiveQid + "</div>" +
        "<div class=\"wd-title\">" + esc(mention ? mention.surface : "") + "</div>" +
        "<a class=\"wd-link\" href=\"https://www.wikidata.org/wiki/" + effectiveQid + "\" target=\"_blank\" style=\"margin-top:8px;display:inline-block\">\u2197 Wikidata</a>" +
        wgaLinkHtml();
      showArtImage(effectiveQid);
    } else if (wgaId) {
      wdP.innerHTML =
        "<div class=\"wd-title\">" + esc(mention ? mention.surface : "") + "</div>" +
        wgaLinkHtml();
      showArtImage(null);
    } else {
      wdP.innerHTML = "<div class=\"wd-empty\">No linked data for this mention</div>";
    }

    // Graph
    document.getElementById("graph-empty").style.display="none";
    document.getElementById("g-info").style.display="none";
    buildMentionGraph(id);
  }

  function doClear(){
    clearTimeout(scanTimer);clearTimeout(typeTimer);
    clearFacHighlight();
    document.querySelectorAll(".ann").forEach(function(a){a.classList.remove("lit");a.classList.remove("pick");a.classList.remove("graph-highlight");});
    document.getElementById("fb").classList.remove("on");
    document.getElementById("tb").classList.remove("on");
    document.getElementById("bscan").classList.remove("active");
    document.getElementById("st").textContent="Ready";
    document.getElementById("detail").classList.remove("open");
    document.getElementById("vasari-wrap").classList.remove("risen");
    document.getElementById("bubble").textContent="";
    document.getElementById("g-edges").innerHTML="";
    document.getElementById("g-nodes").innerHTML="";
    document.getElementById("graph-empty").style.display="flex";
    document.getElementById("g-info").style.display="none";
    document.getElementById("graph-title").textContent="Click a mention to see its provenance graph";
    var artI=document.getElementById("art-img");
    artI.classList.remove("risen"); artI.src=""; artI.style.display="block";
    document.getElementById("wd-panel").innerHTML="<div class=\"wd-empty\">Select a mention to see linked data</div>";
  }

  // Keyboard navigation for facsimile booklet
  document.addEventListener("keydown", function(ev) {
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT" || ev.target.tagName === "TEXTAREA") return;
    if (ev.key === "ArrowLeft" && FAC_PAGES.length) { facShow(facIdx - 1, true); ev.preventDefault(); }
    if (ev.key === "ArrowRight" && FAC_PAGES.length) { facShow(facIdx + 1, true); ev.preventDefault(); }
  });

  window.VSR        = { open: openDetail };
  window.startScan  = startScan;
  window.revealAll  = revealAll;
  window.clearAll   = doClear;
  window.resetGraphZoom = resetGraphZoom;

  buildText();

  // ── Facsimile annotation overlay (OCR-based) ────────────────────────
  function buildFacOverlay(pageNum) {
    if (!facOverlay) return;
    facOverlay.innerHTML = "";
    facRects = [];

    var hl = OCR_HL[String(pageNum)];
    if (!hl || !hl.rects || !hl.rects.length) return;

    var imgW = hl.img_w, imgH = hl.img_h;
    if (!imgW || !imgH) return;

    // Size overlay to match the rendered image
    var img = document.getElementById("fac-img");
    if (img) {
      facOverlay.style.width  = img.offsetWidth  + "px";
      facOverlay.style.height = img.offsetHeight + "px";
    }

    for (var i = 0; i < hl.rects.length; i++) {
      var r = hl.rects[i];
      var rect = document.createElement("div");
      rect.className = "fac-rect " + r.type;
      rect.dataset.id = r.mid;
      // Position as percentage of original image dimensions
      rect.style.left   = (r.x / imgW * 100) + "%";
      rect.style.top    = (r.y / imgH * 100) + "%";
      rect.style.width  = (r.w / imgW * 100) + "%";
      rect.style.height = (r.h / imgH * 100) + "%";
      facOverlay.appendChild(rect);
      facRects.push({ el: rect, mid: r.mid });
    }
  }

  function highlightFacMention(mentionId) {
    // Check if mention is on the current page
    var onCurrent = false;
    for (var i = 0; i < facRects.length; i++) {
      if (facRects[i].mid === mentionId) { onCurrent = true; break; }
    }

    if (!onCurrent) {
      // Find which page has this mention
      var targetPage = null;
      for (var p in OCR_HL) {
        var rects = OCR_HL[p].rects || [];
        for (var j = 0; j < rects.length; j++) {
          if (rects[j].mid === mentionId) { targetPage = p; break; }
        }
        if (targetPage) break;
      }
      if (targetPage) {
        // Switch page — highlight will apply after image loads
        pendingHighlight = mentionId;
        var pageIdx = FAC_PAGES.indexOf(parseInt(targetPage));
        if (pageIdx !== -1) {
          facShow(pageIdx, false);
          return;
        }
      }
    }

    // Clear previous and show match
    for (var i = 0; i < facRects.length; i++) {
      facRects[i].el.classList.remove("visible");
    }
    for (var i = 0; i < facRects.length; i++) {
      if (facRects[i].mid === mentionId) facRects[i].el.classList.add("visible");
    }
  }

  function clearFacHighlight() {
    for (var i = 0; i < facRects.length; i++) {
      facRects[i].el.classList.remove("visible");
    }
  }

  // ── Auto-highlight mention from ?highlight= param (KG explorer link) ──
  var hlParam = new URLSearchParams(window.location.search).get("highlight");
  if(hlParam){
    var hlLower = hlParam.toLowerCase();
    // Find matching mention by surface form or label
    setTimeout(function(){
      var best = null;
      var bestEl = null;
      document.querySelectorAll(".ann[data-id]").forEach(function(el){
        var mid = el.getAttribute("data-id");
        var m = MENTIONS[mid];
        if(!m) return;
        var surface = (m.surface||"").toLowerCase();
        var label = (m.label||"").toLowerCase();
        if(surface === hlLower || label === hlLower ||
           surface.indexOf(hlLower) >= 0 || hlLower.indexOf(surface) >= 0 ||
           (label && (label.indexOf(hlLower) >= 0 || hlLower.indexOf(label) >= 0))){
          if(!best || m.type.indexOf("explicit") >= 0){
            best = mid;
            bestEl = el;
          }
        }
      });
      if(bestEl){
        // Reveal all mentions first so the highlight is visible
        revealAll();
        // Scroll into view and open detail
        setTimeout(function(){
          bestEl.scrollIntoView({behavior:"smooth", block:"center"});
          openDetail(bestEl);
        }, 300);
      }
    }, 200);
  }
}());