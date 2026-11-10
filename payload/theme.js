// The fire section's behaviour. window.FIRE holds its real data, written at build time.
// Every action answers at once, rewards vary in size, and nothing punishes being away.
(function () {
  "use strict";
  const F = window.FIRE;
  if (!F) return;
  const $ = (id) => document.getElementById(id);
  const root = document.documentElement;
  const isCalm = () => root.classList.contains("calm");
  // Every stored key carries this workspace's id, so two dashboards in one browser never share state.
  const key = (name) => window.DASH_NS + "-" + name;
  // One feature failing must not stop the others.
  const part = (feature) => { try { feature(); } catch (error) { console.error(error); } };
  const randomIndex = (length, not) => {
    if (length < 2) return 0;
    let index = Math.floor(Math.random() * length);
    if (index === not) index = (index + 1) % length;
    return index;
  };
  function store(area, name, value) {
    try { if (value === undefined) return area.getItem(key(name)); area.setItem(key(name), value); } catch (error) { return null; }
    return null;
  }

  // The page reloads once a minute. What you were looking at comes back with it.
  let state = {};
  try { state = JSON.parse(store(sessionStorage, "state") || "{}"); } catch (error) { state = {}; }
  const firstOpen = !state.opened;
  const autoReload = !!state.auto;
  const pick = (name, length) => {
    if (!Number.isInteger(state[name]) || state[name] < 0 || state[name] >= length) state[name] = randomIndex(length);
    return state[name];
  };
  function saveState(auto) {
    state.opened = true;
    state.auto = !!auto;
    state.scroll = window.scrollY;
    state.open = [...document.querySelectorAll("details")].filter((d) => d.open)
      .map((d) => d.querySelector("summary").firstChild.textContent);
    state.panes = [...document.querySelectorAll(".scroll, aside")].map((el) => el.scrollTop);
    store(sessionStorage, "state", JSON.stringify(state));
  }
  window.beforePageReload = () => saveState(true);
  addEventListener("pagehide", () => { if (!state.auto) saveState(false); });
  if (autoReload) {
    const open = new Set(state.open || []);
    document.querySelectorAll("details").forEach((d) => {
      if (open.has(d.querySelector("summary").firstChild.textContent)) d.open = true;
    });
    document.querySelectorAll(".scroll, aside").forEach((el, i) => { el.scrollTop = (state.panes || [])[i] || 0; });
    window.scrollTo(0, state.scroll || 0);
  }
  state.auto = false;

  // The switch in the header. The fire is on by default whatever the browser's reduce-motion signal says,
  // unless dashboard_config.json sets motion to respect-os. See the kit's START_HERE.md for why.
  const calmButton = $("calm-toggle");
  function showCalm() { calmButton.textContent = isCalm() ? "Light the fire" : "Stop the fire"; }
  calmButton.addEventListener("click", () => {
    root.classList.toggle("calm");
    store(localStorage, "calm", isCalm() ? "1" : "0");
    showCalm();
  });
  showCalm();

  // Sparks: a trail from the pointer and a burst on every click, so each action gets an answer.
  let lastSpark = 0, sparks = 0;
  function spark(x, y, spread) {
    if (sparks > 44) return;
    const s = document.createElement("span");
    s.className = "spark" + (Math.random() < 0.3 ? " red" : "");
    s.textContent = "✦✧*"[Math.floor(Math.random() * 3)];
    s.style.left = x + "px";
    s.style.top = y + "px";
    const angle = Math.random() * Math.PI * 2, reach = spread * (0.4 + Math.random());
    s.style.setProperty("--dx", Math.cos(angle) * reach + "px");
    s.style.setProperty("--dy", Math.sin(angle) * reach + (spread < 40 ? 34 : 10) + "px");
    s.addEventListener("animationend", () => { s.remove(); sparks--; });
    document.body.append(s);
    sparks++;
  }
  addEventListener("mousemove", (event) => {
    const now = performance.now();
    if (isCalm() || now - lastSpark < 40) return;
    lastSpark = now;
    spark(event.clientX, event.clientY, 22);
  }, { passive: true });
  addEventListener("click", (event) => {
    if (isCalm()) return;
    for (let i = 0; i < 12; i++) spark(event.clientX, event.clientY, 70);
  });

  // The painting and its line change together, on their own and at a click.
  const artFigure = $("art-figure"), artA = $("art-a"), artB = $("art-b"), artTitle = $("art-title");
  const lineEl = $("line"), lineFrom = $("line-from");
  let front = artA;
  function showPainting(index, animate) {
    const art = F.art[index];
    state.art = index;
    artTitle.textContent = art.title;
    $("art-credit").textContent = art.credit;
    const incoming = animate ? (front === artA ? artB : artA) : front;
    incoming.src = art.src;
    incoming.alt = art.credit + ": " + art.title;
    incoming.style.objectPosition = art.focus;
    if (animate) {
      incoming.classList.remove("off");
      front.classList.add("off");
      front = incoming;
      artFigure.classList.add("flare");
      setTimeout(() => artFigure.classList.remove("flare"), 1300);
    }
  }
  function showLine(index, animate) {
    const line = F.lines[index];
    state.line = index;
    lineEl.textContent = line.placeholder ? line.text : "“" + line.text + "”";
    lineEl.classList.toggle("placeholder", !!line.placeholder);
    lineFrom.textContent = line.who;
    lineFrom.href = line.href;
    if (animate) { lineEl.classList.remove("swap"); void lineEl.offsetWidth; lineEl.classList.add("swap"); }
  }
  part(() => {
    if (F.art.length) showPainting(pick("art", F.art.length), false);
    if (F.lines.length) {
      showLine(pick("line", F.lines.length), false);
    } else {
      lineEl.hidden = true;
      $("line-box").hidden = true;
    }
    $("art-next").addEventListener("click", () => { if (F.art.length) showPainting((state.art + 1) % F.art.length, true); });
    $("line-next").addEventListener("click", () => { if (F.lines.length) showLine((state.line + 1) % F.lines.length, true); });
    setInterval(() => {
      if (document.hidden || isCalm()) return;
      if (F.art.length) showPainting((state.art + 1) % F.art.length, true);
      if (F.lines.length) showLine((state.line + 1) % F.lines.length, true);
    }, 30000);
  });

  // Spark and Campfire: real things from the ledger and the project list, with a die to change your mind.
  function showPick(el, text, title, animate) {
    el.replaceChildren();
    if (title) { const b = document.createElement("b"); b.textContent = title; el.append(b); }
    el.append(text);
    if (animate) { el.classList.remove("swap"); void el.offsetWidth; el.classList.add("swap"); }
  }
  function goProject(id) {
    const card = document.getElementById(id);
    if (!card) return;
    card.scrollIntoView({ behavior: isCalm() ? "auto" : "smooth", block: "center" });
    card.classList.remove("flash");
    void card.offsetWidth;
    card.classList.add("flash");
  }
  function setupRoll(name, pool, el, render) {
    const button = $(name + "-roll");
    if (!pool.length) { el.textContent = "Nothing here right now."; button.hidden = true; return; }
    render(pool[pick(name, pool.length)], false);
    button.addEventListener("click", () => {
      button.classList.remove("rolling"); void button.offsetWidth; button.classList.add("rolling");
      state[name] = randomIndex(pool.length, state[name]);
      render(pool[state[name]], true);
    });
  }
  part(() => setupRoll("spark", F.sparks, $("spark"), (item, animate) => showPick($("spark"), item, "", animate)));
  const campGo = $("campfire-go");
  campGo.hidden = !F.camps.length;
  part(() => setupRoll("campfire", F.camps, $("campfire"), (item, animate) => {
    showPick($("campfire"), item.next, item.name, animate);
    campGo.href = "#" + item.id;
    campGo.onclick = (event) => { event.preventDefault(); goProject(item.id); };
  }));

  // Beacon: each rune names its project, and going there lights the card up.
  const tip = $("ring-tip"), tipDefault = tip.innerHTML;
  document.querySelectorAll(".rune").forEach((rune) => {
    const show = () => {
      tip.textContent = rune.dataset.name;
      const small = document.createElement("small");
      small.textContent = rune.dataset.status;
      tip.append(small);
    };
    rune.addEventListener("mouseenter", show);
    rune.addEventListener("focus", show);
    rune.addEventListener("mouseleave", () => { tip.innerHTML = tipDefault; });
    rune.addEventListener("blur", () => { tip.innerHTML = tipDefault; });
    rune.addEventListener("click", (event) => { event.preventDefault(); goProject(rune.dataset.id); });
  });

  // Webring: wander the projects, including the ones you had forgotten about.
  part(() => {
    if (!F.projects.length) { document.querySelector(".ring-nav").hidden = true; return; }
    let ringAt = pick("ringAt", F.projects.length);
    function ringGo(index) {
      ringAt = (index + F.projects.length) % F.projects.length;
      state.ringAt = ringAt;
      goProject(F.projects[ringAt]);
    }
    $("ring-prev").addEventListener("click", () => ringGo(ringAt - 1));
    $("ring-next").addEventListener("click", () => ringGo(ringAt + 1));
    $("ring-random").addEventListener("click", () => ringGo(randomIndex(F.projects.length, ringAt)));
  });

  // Comments from the friends. Each one quotes a real number or is plainly a placeholder.
  part(() => {
  const commentsEl = $("comments");
  const shown = 3;
  const hour = new Date().getHours();
  let wall = F.comments.slice();
  if (F.late && hour < 5) {
    const clock = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    wall = [{ name: F.late.name, pic: F.late.pic, text: F.late.says.replace("{clock}", clock) }, ...wall];
  }
  if (!wall.length) { $("more-comments").hidden = true; commentsEl.textContent = "Nobody has said anything yet."; return; }
  let wallAt = pick("wall", wall.length);
  function commentRow(comment, fresh) {
    const row = document.createElement("div");
    row.className = "comment" + (fresh ? " swap" : "");
    const pic = document.createElement("img");
    pic.src = comment.pic;
    pic.alt = "";
    const body = document.createElement("div");
    const name = document.createElement("b");
    name.textContent = comment.name;
    const text = document.createElement("p");
    text.textContent = comment.text;
    body.append(name, text);
    row.append(pic, body);
    return row;
  }
  function showComments(start, fresh) {
    wallAt = (start + wall.length) % wall.length;
    state.wall = wallAt;
    const rows = [];
    for (let i = 0; i < Math.min(shown, wall.length); i++) rows.push(commentRow(wall[(wallAt + i) % wall.length], fresh && i === 0));
    commentsEl.replaceChildren(...rows);
  }
  showComments(hour < 5 && F.late && firstOpen ? 0 : wallAt, false);
  $("more-comments").addEventListener("click", () => showComments(wallAt + shown, true));
  setInterval(() => { if (!document.hidden && !isCalm()) showComments(wallAt + 1, true); }, 11000);
  document.querySelectorAll(".friend button").forEach((button) => {
    button.addEventListener("click", () => {
      const index = wall.findIndex((c) => c.name === button.dataset.name);
      if (index >= 0) showComments(index, true);
      commentsEl.scrollIntoView({ behavior: isCalm() ? "auto" : "smooth", block: "nearest" });
    });
  });
  });

  // Hit counter: a true count of opens in this browser. It goes up and is never used against you.
  function setOdometer(el, value) {
    const digits = String(value).padStart(el.children.length, "0");
    [...el.children].forEach((cell, i) => { cell.textContent = digits[digits.length - el.children.length + i]; });
  }
  part(() => {
  const hits = $("hits");
  let hitCount = parseInt(store(localStorage, "hits"), 10) || 0;
  if (!autoReload) { hitCount++; store(localStorage, "hits", String(hitCount)); }
  setOdometer(hits, Math.max(hitCount, 1));
  if (firstOpen && !isCalm()) {
    document.querySelectorAll(".odo[data-value]").forEach((el) => {
      const target = parseInt(el.dataset.value, 10);
      const started = performance.now();
      const tick = (now) => {
        const share = Math.min(1, (now - started) / 1500);
        setOdometer(el, Math.round(target * (1 - Math.pow(1 - share, 3))));
        if (share < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }
  });

  // A rare surprise, and a word that brings out a crowd for anyone who types it.
  function mascots(count) {
    if (isCalm() || !F.mascot) return;
    for (let i = 0; i < count; i++) {
      const hop = document.createElement("div");
      hop.className = "hop";
      hop.style.setProperty("--t", 6 + Math.random() * 5 + "s");
      hop.style.setProperty("--wait", i * 0.5 + "s");
      const img = document.createElement("img");
      img.src = F.mascot.img;
      img.alt = "";
      hop.append(img);
      hop.addEventListener("animationend", (event) => { if (event.target === hop) hop.remove(); });
      document.body.append(hop);
    }
  }
  if (!autoReload && Math.random() < 1 / 6) setTimeout(() => mascots(1), 2500);
  let typed = "";
  addEventListener("keydown", (event) => {
    if (!F.mascot || !F.mascot.word || (event.target && event.target.tagName === "INPUT")) return;
    typed = (typed + (event.key || "")).slice(-F.mascot.word.length).toLowerCase();
    if (typed === F.mascot.word) { typed = ""; mascots(12); }
  });

  // The profile song. It never plays until asked. An original tune in A minor; a reload waits for it to stop.
  let audio = null, songTimer = null;
  const songBox = $("song"), songButton = $("song-play");
  window.pageBusy = () => audio !== null;
  const midi = (n) => 440 * Math.pow(2, (n - 69) / 12);
  const LEAD = [69,0,72,0,76,0,74,72, 72,0,69,0,65,0,69,72, 76,0,79,0,84,0,79,76, 74,0,71,74,79,0,0,0,
    81,0,79,76,72,0,76,0, 77,0,76,72,69,0,72,0, 74,0,76,77,79,0,77,76, 76,74,72,71,69,0,0,0];
  const CHORDS = [[45,57,60,64],[41,53,57,60],[48,55,60,64],[43,55,59,62],[45,57,60,64],[41,53,57,60],[43,55,59,62],[45,57,60,64]];
  function note(n, when, length, type, level) {
    const osc = audio.createOscillator(), gain = audio.createGain();
    osc.type = type;
    osc.frequency.value = midi(n);
    gain.gain.setValueAtTime(level, when);
    gain.gain.exponentialRampToValueAtTime(0.001, when + length);
    osc.connect(gain).connect(audio.master);
    osc.start(when);
    osc.stop(when + length + 0.02);
  }
  function startSong() {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return;
    audio = new Context();
    audio.master = audio.createGain();
    audio.master.gain.value = 0.5;
    audio.master.connect(audio.destination);
    const eighth = 60 / 132 / 2;
    let at = 0, when = audio.currentTime + 0.06;
    songTimer = setInterval(() => {
      while (when < audio.currentTime + 0.25) {
        const chord = CHORDS[Math.floor(at / 8) % 8];
        if (LEAD[at]) note(LEAD[at], when, eighth * 1.7, "square", 0.05);
        note(chord[1 + at % 3], when, eighth * 0.9, "triangle", 0.09);
        if (at % 4 === 0) note(chord[0], when, eighth * 3.5, "sawtooth", 0.05);
        at = (at + 1) % LEAD.length;
        when += eighth;
      }
    }, 60);
    songBox.classList.add("playing");
    songButton.textContent = "■ stop";
  }
  function stopSong() {
    clearInterval(songTimer);
    audio.close();
    audio = null;
    songBox.classList.remove("playing");
    songButton.textContent = "▶ play";
  }
  songButton.addEventListener("click", () => (audio ? stopSong() : startSong()));
})();
