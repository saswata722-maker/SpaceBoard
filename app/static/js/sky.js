/* SpaceBoard sky map — interactive 2D planisphere.
 *
 * Geometry: RA/Dec degrees on canvas (projectRaDec), so the star catalog and
 * the constellation line file can be plotted directly.
 * Ephemeris: astronomy-engine, only through calls verified against its source:
 *   Equator(body, time, observer, ofdate, aberration) -> {ra in HOURS, dec, dist}
 *   Horizon(time, observer, raHours, decDeg, 'normal') -> {altitude, azimuth}
 *   Constellation(raHoursJ2000, decDeg)                -> {symbol, name}
 *   MakeTime(date), SiderealTime(date) -> GST in hours
 * Anything the engine cannot do degrades to a text message; nothing throws.
 */
'use strict';
(function () {

    var Astronomy = window.Astronomy;  // undefined if the CDN script fails
    var ENGINE_URL = 'https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js';
    var AU_KM = 149597870.7;

    var canvas = document.getElementById('sky-canvas');
    var ctx = canvas.getContext('2d');
    var loadingOverlay = document.getElementById('loading-overlay');
    var infoPanel = document.getElementById('info-panel');
    var infoName = document.getElementById('info-name');
    var infoType = document.getElementById('info-type');
    var infoMag = document.getElementById('info-mag');
    var infoConst = document.getElementById('info-const');
    var infoDist = document.getElementById('info-dist');
    var infoElev = document.getElementById('info-elev');
    var infoClose = document.getElementById('info-close');
    var hoverTooltip = document.getElementById('hover-tooltip');
    var obsTimeInput = document.getElementById('obs-time');
    var timeSlider = document.getElementById('time-slider');
    var latInput = document.getElementById('latitude');
    var lonInput = document.getElementById('longitude');
    var locateBtn = document.getElementById('locate-btn');
    var zoomSlider = document.getElementById('zoom-slider');
    var zoomLevel = document.getElementById('zoom-level');
    var centerRah = document.getElementById('center-rah');
    var centerExt = document.getElementById('center-ext');
    var centerAlt = document.getElementById('center-alt');
    var centerAz = document.getElementById('center-az');
    var showPlanetsCb = document.getElementById('show-planets');
    var showEclipticCb = document.getElementById('show-ecliptic');
    var showGridCb = document.getElementById('show-grid');
    var showNamesCb = document.getElementById('show-names');
    var showConstellationsCb = document.getElementById('show-constellations');
    var dirBtns = document.querySelectorAll('.view-dir-btn');
    var animPlayBtn = document.getElementById('anim-play-btn');
    var animPlayIcon = document.getElementById('anim-play-icon');
    var animPlayText = document.getElementById('anim-play-text');
    var animSpeedSelect = document.getElementById('anim-speed');
    var timeNowBtn = document.getElementById('time-now-btn');


    var DEG = Math.PI / 180;
    var RAD = 180 / Math.PI;
    var PIXELS_PER_DEG = 4;

    // Bodies the engine can compute, keyed by the name returned by the API.
    var BODY_BY_NAME = {
        sun: 'Sun', moon: 'Moon',
        mercury: 'Mercury', venus: 'Venus', mars: 'Mars', jupiter: 'Jupiter',
        saturn: 'Saturn', uranus: 'Uranus', neptune: 'Neptune', pluto: 'Pluto'
    };

    var state = {
        stars: [], constellations: [], planets: [],
        lat: 40.7128, lon: -74.0060,
        utcTime: new Date(),
        centerRa: 0, centerDec: 45,
        fovDeg: 180,
        selectedObject: null, hoveredObject: null,
        dragging: false, dragX: 0, dragY: 0
        animating: false,
        animSpeed: 3600,
        lastAnimTs: 0

    };

    function bodyFor(name) {
        if (!Astronomy || !name) return null;
        var key = String(name).toLowerCase();
        return BODY_BY_NAME[key] ? Astronomy.Body[BODY_BY_NAME[key]] : null;
    }

    function engineTime() {
        return Astronomy ? Astronomy.MakeTime(new Date(state.utcTime)) : null;
    }

    function observer() {
        return Astronomy ? new Astronomy.Observer(state.lat, state.lon, 0) : null;
    }

    function cssSize() {
        var rect = canvas.parentElement.getBoundingClientRect();
        return {
            w: rect.width,
            h: rect.height,
            dpr: window.devicePixelRatio || 1
        };
    }

    // ---------------------------------------------------------------- layout

    function initTime() {
        var nowDate = new Date();
        var y = nowDate.getFullYear(), m = String(nowDate.getMonth() + 1).padStart(2, '0'),
            d = String(nowDate.getDate()).padStart(2, '0'),
            h = String(nowDate.getHours()).padStart(2, '0'),
            min = String(nowDate.getMinutes()).padStart(2, '0');
        obsTimeInput.value = y + '-' + m + '-' + d + 'T' + h + ':' + min;
        state.utcTime = nowDate;
        if (timeSlider) timeSlider.value = nowDate.getHours() + nowDate.getMinutes() / 60;
    }
    initTime();

    function resizeCanvas() {
        var size = cssSize();
        canvas.width = size.w * size.dpr;
        canvas.height = size.h * size.dpr;
        canvas.style.width = size.w + 'px';
        canvas.style.height = size.h + 'px';
        ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
        render();
    }
    window.addEventListener('resize', resizeCanvas);

    function projectRaDec(ra, dec) {
        var dRa = ra - state.centerRa;
        while (dRa > 180) dRa -= 360;
        while (dRa < -180) dRa += 360;
        var dDec = dec - state.centerDec;
        var scale = PIXELS_PER_DEG * (state.fovDeg / 180);
        var size = cssSize();
        return { x: size.w / 2 + dRa * scale, y: size.h / 2 - dDec * scale };
    }

    // ------------------------------------------------------------------ data

    function hideLoading(message, isError) {
        if (!loadingOverlay) return;
        loadingOverlay.innerHTML = isError
            ? '<p class="text-red-400">' + message + '</p>'
            : '<p class="text-gray-400">' + message + '</p>';
        if (!isError) loadingOverlay.style.display = 'none';
    }

    function loadStars() {
        return fetch('/static/data/stars.json')
            .then(function (r) { return r.json(); })
            .then(function (data) { state.stars = data; hideLoading(''); render(); })
            .catch(function (err) {
                console.error('Failed to load star catalog:', err);
                hideLoading('Failed to load star catalog.', true);
            });
    }

    function loadConstellations() {
        return fetch('/static/data/constellations.json')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                state.constellations = (data && data.constellations) || [];
                render();
            })
            .catch(function (err) {
                console.warn('Constellation lines unavailable:', err);
                state.constellations = [];
            });
    }

    function loadPlanets() {
        return fetch('/sky/api/planet-positions')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                state.planets = (data && data.ok) ? data.planets : [];
                if (state.planets.length) {
                    state.planets.push({ id: 'sun', name: 'Sun' });
                    state.planets.push({ id: 'moon', name: 'Moon' });
                }
                if (data && !data.ok) console.warn('Planet data unavailable:', data.error);
                render();
            })
            .catch(function (err) { console.warn('Failed to load planet data:', err); });
    }

    // ------------------------------------------------------------- ephemeris

    /** Of-date RA/Dec (RA returned in HOURS by the engine) plus alt/az. */
    function bodyPosition(body) {
        if (!Astronomy) return null;
        var time = engineTime();
        var obs = observer();
        try {
            var equ = Astronomy.Equator(body, time, obs, true, true);
            var hor = Astronomy.Horizon(time, obs, equ.ra, equ.dec, 'normal');
            return {
                ra: equ.ra * 15,          // projectRaDec works in degrees
                dec: equ.dec,
                distAu: equ.dist,
                alt: hor.altitude,
                az: hor.azimuth
            };
        } catch (err) {
            console.warn('Position unavailable for body:', err);
            return null;
        }
    }

    /** Local sidereal time in degrees: SiderealTime() returns GST in hours. */
    function localSiderealTimeDegrees() {
        if (!Astronomy) return null;
        var gst = Astronomy.SiderealTime(engineTime());
        return ((gst * 15 + state.lon) % 360 + 360) % 360;
    }

    /** Alt/az of an arbitrary RA/Dec (degrees) for the center-of-view readout. */
    function altAzOf(raDeg, decDeg) {
        var lst = localSiderealTimeDegrees();
        if (lst === null) return null;
        var ha = (lst - raDeg) * DEG;
        var lat = state.lat * DEG, dec = decDeg * DEG;
        var sinAlt = Math.sin(lat) * Math.sin(dec) +
                     Math.cos(lat) * Math.cos(dec) * Math.cos(ha);
        sinAlt = Math.max(-1, Math.min(1, sinAlt));
        var alt = Math.asin(sinAlt);
        var cosAz = (Math.sin(dec) - Math.sin(lat) * sinAlt) /
                    (Math.cos(lat) * Math.cos(alt));
        var az = Math.acos(Math.max(-1, Math.min(1, cosAz)));
        if (Math.sin(ha) > 0) az = 2 * Math.PI - az;
        return { alt: alt * RAD, az: (360 - az * RAD) % 360 };
    }

    /** IAU constellation for J2000 coordinates; the engine wants RA in hours. */
    function constellationOf(raDeg, decDeg) {
        if (!Astronomy) return null;
        try {
            var c = Astronomy.Constellation(((raDeg / 15) % 24 + 24) % 24, decDeg);
            return c ? c.name + ' (' + c.symbol + ')' : null;
        } catch (err) {
            return null;
        }
    }

    function formatDistance(au) {
        if (au === null || au === undefined) return '\u2014';
        if (au < 0.01) return Math.round(au * AU_KM).toLocaleString() + ' km';
        return au.toFixed(2) + ' AU';
    }

    // ---------------------------------------------------------------- render

    function render() {
        var size = cssSize();
        ctx.clearRect(0, 0, size.w, size.h);

        var grad = ctx.createRadialGradient(size.w / 2, size.h / 2, 0,
                                            size.w / 2, size.h / 2, Math.max(size.w, size.h) / 2);
        grad.addColorStop(0, '#0d1117');
        grad.addColorStop(1, '#000000');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, size.w, size.h);

        if (showGridCb && showGridCb.checked) drawGrid(size.w, size.h);
        if (showEclipticCb && showEclipticCb.checked) drawEcliptic(size.w, size.h);
        if (showConstellationsCb && showConstellationsCb.checked) drawConstellations();
        drawStars(size.w, size.h);
        if (showConstellationsCb && showConstellationsCb.checked) drawConstellationLabels();
        if (showPlanetsCb && showPlanetsCb.checked) drawPlanets();

        if (state.selectedObject) {
            var p = projectRaDec(state.selectedObject.ra, state.selectedObject.dec);
            ctx.beginPath();
            ctx.arc(p.x, p.y, 8, 0, 2 * Math.PI);
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
        updateCenterInfo();
    }

    function drawGrid(w, h) {
        ctx.strokeStyle = 'rgba(255,255,255,0.07)';
        ctx.lineWidth = 1;
        for (var ra = 0; ra < 360; ra += 15) {
            var p = projectRaDec(ra, 0);
            ctx.beginPath();
            ctx.moveTo(p.x, 0);
            ctx.lineTo(p.x, h);
            ctx.stroke();
        }
        for (var dec = -75; dec <= 75; dec += 15) {
            var q = projectRaDec(0, dec);
            ctx.beginPath();
            ctx.moveTo(0, q.y);
            ctx.lineTo(w, q.y);
            ctx.stroke();
        }
    }

    /** Ecliptic polyline: convert ecliptic longitude 0..360 to RA/Dec. */
    function drawEcliptic(w, h) {
        ctx.strokeStyle = 'rgba(250,204,21,0.55)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 6]);
        ctx.beginPath();
        var obliquity = 23.43928 * DEG;
        var last = null;
        for (var lon = 0; lon <= 360; lon += 3) {
            var l = lon * DEG;
            var ra = Math.atan2(Math.sin(l) * Math.cos(obliquity), Math.cos(l)) * RAD;
            var dec = Math.asin(Math.sin(l) * Math.sin(obliquity)) * RAD;
            var p = projectRaDec(ra, dec);
            if (last === null || Math.abs(p.x - last.x) > w / 2) {
                ctx.moveTo(p.x, p.y);
            } else {
                ctx.lineTo(p.x, p.y);
            }
            last = p;
        }
        ctx.stroke();
        ctx.setLineDash([]);
    }

    /**
     * Constellation stick figures from static/data/constellations.json.
     * Coordinates are RA/Dec degrees; a segment is broken where it crosses the
     * 0/360 boundary so no line is drawn straight across the canvas.
     */
    function drawConstellations() {
        ctx.strokeStyle = 'rgba(129,140,248,0.55)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (var i = 0; i < state.constellations.length; i++) {
            var lines = state.constellations[i].lines;
            for (var j = 0; j < lines.length; j++) {
                var pts = lines[j];
                var previousRa = null;
                for (var k = 0; k < pts.length; k++) {
                    var p = projectRaDec(pts[k][0], pts[k][1]);
                    if (previousRa === null || Math.abs(pts[k][0] - previousRa) > 180) {
                        ctx.moveTo(p.x, p.y);
                    } else {
                        ctx.lineTo(p.x, p.y);
                    }
                    previousRa = pts[k][0];
                }
            }
        }
        ctx.stroke();
    }

    /**
     * Circular-mean RA/Dec of a constellation's line points — where its name
     * sits. Circular mean keeps wrap-around constellations (near RA 0/360) in
     * the right place instead of dragging the label to the middle of the sky.
     */
    function constellationLabelPoint(constellation) {
        var sinSum = 0, cosSum = 0, decSum = 0, count = 0;
        var lines = constellation.lines;
        for (var i = 0; i < lines.length; i++) {
            for (var j = 0; j < lines[i].length; j++) {
                var ra = lines[i][j][0] * DEG;
                sinSum += Math.sin(ra);
                cosSum += Math.cos(ra);
                decSum += lines[i][j][1];
                count++;
            }
        }
        if (!count) return null;
        var raDeg = Math.atan2(sinSum, cosSum) * RAD;
        if (raDeg < 0) raDeg += 360;
        return { ra: raDeg, dec: decSum / count };
    }

    /**
     * Constellation names, drawn over the stars. Suppressed at wide fields of
     * view where 24 names would overlap into unreadable noise.
     */
    function drawConstellationLabels() {
        if (state.fovDeg > 100) return;
        var size = cssSize();
        ctx.save();
        ctx.textAlign = 'center';
        ctx.font = '12px system-ui, sans-serif';
        for (var i = 0; i < state.constellations.length; i++) {
            var constellation = state.constellations[i];
            if (!constellation._label) {
                constellation._label = constellationLabelPoint(constellation);
            }
            if (!constellation._label) continue;
            var p = projectRaDec(constellation._label.ra, constellation._label.dec);
            if (p.x < 40 || p.y < 20 || p.x > size.w - 40 || p.y > size.h - 20) continue;
            ctx.fillStyle = 'rgba(165,180,252,0.85)';
            ctx.fillText(constellation.name, p.x, p.y);
        }
        ctx.restore();
    }

    /** Star radius from magnitude; brighter stars are larger. */
    function starRadius(mag) {
        var m = (typeof mag === 'number') ? mag : 6;
        return Math.max(0.7, 3.4 - 0.45 * m);
    }

    function drawStars(w, h) {
        var showNames = showNamesCb && showNamesCb.checked;
        for (var i = 0; i < state.stars.length; i++) {
            var s = state.stars[i];
            var p = projectRaDec(s.ra, s.dec);
            if (p.x < -20 || p.y < -20 || p.x > w + 20 || p.y > h + 20) continue;

            var r = starRadius(s.mag);
            var named = !!s.name;
            ctx.beginPath();
            ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = named ? '#f8fafc' : '#cbd5e1';
            ctx.fill();

            if (showNames && named && r > 1.4) {
                ctx.fillStyle = 'rgba(203,213,225,0.9)';
                ctx.font = '11px system-ui, sans-serif';
                ctx.fillText(s.name, p.x + r + 3, p.y + 4);
            }
        }
    }

    function planetColor(name) {
        var key = String(name || '').toLowerCase();
        if (key === 'sun') return '#fde047';
        if (key === 'moon') return '#bfdbfe';
        if (key === 'mars') return '#fca5a5';
        if (key === 'jupiter' || key === 'saturn') return '#fed7aa';
        return '#fde68a';
    }

    /** Planets, Sun and Moon via astronomy-engine; dimmed when below horizon. */
    function drawPlanets() {
        var showNames = showNamesCb && showNamesCb.checked;
        var size = cssSize();
        for (var i = 0; i < state.planets.length; i++) {
            var planet = state.planets[i];
            var body = bodyFor(planet.name || planet.id);
            if (!body) continue;
            var pos = bodyPosition(body);
            if (!pos) continue;

            var p = projectRaDec(pos.ra, pos.dec);
            if (p.x < -30 || p.y < -30 || p.x > size.w + 30 || p.y > size.h + 30) continue;

            var below = pos.alt <= 0;
            var key = String(planet.name || '').toLowerCase();
            var r = key === 'sun' ? 7 : (key === 'moon' ? 5.5 : 4.5);

            ctx.globalAlpha = below ? 0.4 : 1;
            ctx.beginPath();
            ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = planetColor(planet.name);
            ctx.fill();
            ctx.globalAlpha = 1;

            if (showNames) {
                ctx.fillStyle = below ? 'rgba(148,163,184,0.8)' : 'rgba(253,224,71,0.95)';
                ctx.font = '12px system-ui, sans-serif';
                ctx.fillText(planet.name, p.x + r + 4, p.y + 4);
            }

            planet._screen = { x: p.x, y: p.y };
            planet._ra = pos.ra;
            planet._dec = pos.dec;
            planet._alt = pos.alt;
            planet._az = pos.az;
            planet._dist = pos.distAu;
        }
    }

    // ------------------------------------------------------------ interaction

    /** Closest star or planet within `radius` px of (x, y), or null. */
    function findObjectAt(x, y) {
        var radius = 14;
        var best = null, bestDist = radius;

        for (var i = 0; i < state.stars.length; i++) {
            var s = state.stars[i];
            var p = projectRaDec(s.ra, s.dec);
            var d = Math.hypot(p.x - x, p.y - y);
            if (d < bestDist) {
                bestDist = d;
                best = {
                    type: 'star', name: s.name || 'Unnamed star',
                    ra: s.ra, dec: s.dec, mag: s.mag, constellation: s.constellation,
                    distance: null, elevation: null
                };
            }
        }

        if (showPlanetsCb && showPlanetsCb.checked) {
            for (var j = 0; j < state.planets.length; j++) {
                var planet = state.planets[j];
                if (!planet._screen) continue;
                var dp = Math.hypot(planet._screen.x - x, planet._screen.y - y);
                if (dp < bestDist) {
                    bestDist = dp;
                    var info = altAzOf(planet._ra, planet._dec);
                    best = {
                        type: 'planet', name: planet.name,
                        ra: planet._ra, dec: planet._dec, mag: '\u2014',
                        constellation: constellationOf(planet._ra, planet._dec),
                        distance: formatDistance(planet._dist),
                        elevation: info ? info.alt.toFixed(1) + '\u00b0 above horizon' : '\u2014'
                    };
                }
            }
        }
        return best;
    }

    function compassPoint(azimuth) {
        var points = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                      'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
        var i = Math.round((((azimuth % 360) + 360) % 360) / 22.5) % 16;
        return points[i];
    }

    function showInfoPanel(obj) {
        infoName.textContent = obj.name || 'Unknown';
        infoType.textContent = obj.type === 'planet'
            ? (String(obj.name).toLowerCase() === 'sun' ? 'Star' : 'Planet')
            : 'Star';
        infoMag.textContent = (obj.mag === null || obj.mag === undefined) ? '\u2014' : obj.mag;
        infoConst.textContent = constellationOf(obj.ra, obj.dec) || obj.constellation || '\u2014';
        infoDist.textContent = obj.distance || '\u2014';

        var info = altAzOf(obj.ra, obj.dec);
        if (info) {
            infoElev.textContent = info.alt.toFixed(1) + '\u00b0 ' + compassPoint(info.az);
        } else {
            infoElev.textContent = obj.elevation || '\u2014';
        }
        infoPanel.classList.remove('hidden');
    }

    function updateCenterInfo() {
        var raHours = (state.centerRa / 15) % 24;
        if (raHours < 0) raHours += 24;
        var rah = Math.floor(raHours),
            ram = Math.floor((raHours - rah) * 60),
            ras = Math.floor(((raHours - rah) * 60 - ram) * 60);
        centerRah.textContent = 'RA: ' + rah + 'h ' + ram + 'm ' + ras + 's';
        centerExt.textContent = 'Dec: ' + state.centerDec.toFixed(2) + '\u00b0';

        var info = altAzOf(state.centerRa, state.centerDec);
        if (info) {
            centerAlt.textContent = 'Alt: ' + info.alt.toFixed(1) + '\u00b0';
            centerAz.textContent = 'Az: ' + info.az.toFixed(1) + '\u00b0';
        } else {
            centerAlt.textContent = 'Alt: \u2014';
            centerAz.textContent = 'Az: \u2014';
        }
    }

    function setViewDirection(dir) {
        if (dir === 'north') { state.centerRa = 0; state.centerDec = 60; }
        else if (dir === 'south') { state.centerRa = 180; state.centerDec = -20; }
        else if (dir === 'east') { state.centerRa = 90; state.centerDec = 20; }
        else if (dir === 'west') { state.centerRa = 270; state.centerDec = 20; }
        else if (dir === 'zenith') { state.centerRa = currentSiderealRa(); state.centerDec = state.lat; }
        else if (dir === 'nadir') { state.centerRa = currentSiderealRa(); state.centerDec = -state.lat; }

        var active = dir === 'south' ? 'south' : dir;
        Array.prototype.forEach.call(dirBtns, function (btn) {
            var isActive = btn.getAttribute('data-dir') === active;
            btn.classList.toggle('bg-blue-600', isActive);
            btn.classList.toggle('border-blue-500', isActive);
            btn.classList.toggle('text-white', isActive);
            btn.classList.toggle('bg-space-700', !isActive);
            btn.classList.toggle('border-gray-600', !isActive);
            btn.classList.toggle('text-gray-300', !isActive);
        });
        render();
    }

    /** RA (degrees) of the observer's meridian — used for the zenith view. */
    function currentSiderealRa() {
        var lst = localSiderealTimeDegrees();
        return lst === null ? 0 : lst;
    }

    // ---------------------------------------------------------------- events

    function pointerXY(event) {
        var rect = canvas.getBoundingClientRect();
        return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }

    canvas.addEventListener('mousedown', function (event) {
        var p = pointerXY(event);
        state.dragging = true;
        state.dragX = p.x;
        state.dragY = p.y;
        state.dragMoved = 0;
    });

    canvas.addEventListener('mousemove', function (event) {
        var p = pointerXY(event);

        if (state.dragging) {
            var scale = PIXELS_PER_DEG * (state.fovDeg / 180);
            state.centerRa = ((state.centerRa - (p.x - state.dragX) / scale) % 360 + 360) % 360;
            state.centerDec = Math.max(-90, Math.min(90, state.centerDec + (p.y - state.dragY) / scale));
            state.dragX = p.x;
            state.dragY = p.y;
            state.dragMoved += 1;
            hoverTooltip.classList.add('hidden');
            render();
            return;
        }

        var hit = findObjectAt(p.x, p.y);
        if (hit) {
            hoverTooltip.textContent = hit.name;
            hoverTooltip.style.left = (p.x + 12) + 'px';
            hoverTooltip.style.top = (p.y - 10) + 'px';
            hoverTooltip.classList.remove('hidden');
            canvas.style.cursor = 'pointer';
        } else {
            hoverTooltip.classList.add('hidden');
            canvas.style.cursor = 'crosshair';
        }
    });

    window.addEventListener('mouseup', function () {
        state.dragging = false;
    });

    canvas.addEventListener('click', function (event) {
        if (state.dragMoved > 6) return;          // it was a drag, not a click
        var p = pointerXY(event);
        var hit = findObjectAt(p.x, p.y);
        if (hit) {
            state.selectedObject = hit;
            showInfoPanel(hit);
        } else {
            state.selectedObject = null;
            infoPanel.classList.add('hidden');
        }
        render();
    });

    canvas.addEventListener('wheel', function (event) {
        event.preventDefault();
        state.fovDeg = Math.max(10, Math.min(180, state.fovDeg + (event.deltaY > 0 ? 8 : -8)));
        zoomSlider.value = state.fovDeg;
        zoomLevel.textContent = state.fovDeg + '\u00b0';
        render();
    }, { passive: false });

    canvas.addEventListener('touchstart', function (event) {
        if (event.touches.length !== 1) return;
        var rect = canvas.getBoundingClientRect();
        state.dragging = true;
        state.dragX = event.touches[0].clientX - rect.left;
        state.dragY = event.touches[0].clientY - rect.top;
        state.dragMoved = 0;
    }, { passive: true });

    canvas.addEventListener('touchmove', function (event) {
        if (!state.dragging || event.touches.length !== 1) return;
        event.preventDefault();
        var rect = canvas.getBoundingClientRect();
        var x = event.touches[0].clientX - rect.left;
        var y = event.touches[0].clientY - rect.top;
        var scale = PIXELS_PER_DEG * (state.fovDeg / 180);
        state.centerRa = ((state.centerRa - (x - state.dragX) / scale) % 360 + 360) % 360;
        state.centerDec = Math.max(-90, Math.min(90, state.centerDec + (y - state.dragY) / scale));
        state.dragX = x;
        state.dragY = y;
        render();
    }, { passive: false });

    canvas.addEventListener('touchend', function () {
        state.dragging = false;
    });

    // ------------------------------------------------------------- controls

    function toLocalInput(date) {
        var y = date.getFullYear(), m = String(date.getMonth() + 1).padStart(2, '0'),
            d = String(date.getDate()).padStart(2, '0'),
            h = String(date.getHours()).padStart(2, '0'),
            min = String(date.getMinutes()).padStart(2, '0');
        return y + '-' + m + '-' + d + 'T' + h + ':' + min;
    }

    function applyTime() {
        state.selectedObject = null;
        infoPanel.classList.add('hidden');
        render();
    }

    function stopAnimation() {
        if (!state.animating) return;
        state.animating = false;
        if (animPlayIcon) animPlayIcon.innerHTML = '&#9658;';
        if (animPlayText) animPlayText.textContent = 'Play';
        if (animPlayBtn) {
            animPlayBtn.classList.remove('bg-blue-600', 'border-blue-500');
            animPlayBtn.classList.add('bg-space-700', 'border-gray-600');
        }
    }

    function startAnimation() {
        if (state.animating) return;
        state.animating = true;
        state.lastAnimTs = performance.now();
        if (animPlayIcon) animPlayIcon.innerHTML = '&#10074;&#10074;';
        if (animPlayText) animPlayText.textContent = 'Pause';
        if (animPlayBtn) {
            animPlayBtn.classList.remove('bg-space-700', 'border-gray-600');
            animPlayBtn.classList.add('bg-blue-600', 'border-blue-500');
        }
        requestAnimationFrame(animStep);
    }

    function toggleAnimation() {
        if (state.animating) stopAnimation();
        else startAnimation();
    }

    function animStep(ts) {
        if (!state.animating) return;
        var dtSec = (ts - state.lastAnimTs) / 1000;
        state.lastAnimTs = ts;
        // Cap dt to 0.2s so background tab freezes do not jump forward wildly
        if (dtSec > 0.2) dtSec = 0.2;

        var msToAdd = dtSec * state.animSpeed * 1000;
        state.utcTime = new Date(state.utcTime.getTime() + msToAdd);

        if (obsTimeInput) obsTimeInput.value = toLocalInput(state.utcTime);
        if (timeSlider) {
            timeSlider.value = state.utcTime.getHours() + state.utcTime.getMinutes() / 60;
        }

        render();
        requestAnimationFrame(animStep);
    }

    if (animPlayBtn) {
        animPlayBtn.addEventListener('click', toggleAnimation);
    }

    if (animSpeedSelect) {
        animSpeedSelect.addEventListener('change', function () {
            state.animSpeed = parseFloat(animSpeedSelect.value) || 3600;
        });
    }

    if (timeNowBtn) {
        timeNowBtn.addEventListener('click', function () {
            stopAnimation();
            var nowDate = new Date();
            state.utcTime = nowDate;
            if (obsTimeInput) obsTimeInput.value = toLocalInput(nowDate);
            if (timeSlider) timeSlider.value = nowDate.getHours() + nowDate.getMinutes() / 60;
            applyTime();
        });
    }


    if (timeSlider) {
        timeSlider.addEventListener('input', function () {
            stopAnimation();

            var hours = parseFloat(timeSlider.value) || 0;
            var base = new Date();
            base.setHours(0, 0, 0, 0);
            state.utcTime = new Date(base.getTime() + hours * 3600000);
            obsTimeInput.value = toLocalInput(state.utcTime);
            applyTime();
        });
    }

    obsTimeInput.addEventListener('change', function () {
        stopAnimation();

        if (!obsTimeInput.value) return;
        state.utcTime = new Date(obsTimeInput.value);
        timeSlider.value = state.utcTime.getHours() + state.utcTime.getMinutes() / 60;
        applyTime();
    });

    latInput.addEventListener('change', function () {
        var value = parseFloat(latInput.value);
        if (!isNaN(value) && value >= -90 && value <= 90) {
            state.lat = value;
            render();
        }
    });

    lonInput.addEventListener('change', function () {
        var value = parseFloat(lonInput.value);
        if (!isNaN(value) && value >= -180 && value <= 180) {
            state.lon = value;
            render();
        }
    });

    locateBtn.addEventListener('click', function () {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                state.lat = pos.coords.latitude;
                state.lon = pos.coords.longitude;
                latInput.value = state.lat.toFixed(4);
                lonInput.value = state.lon.toFixed(4);
                render();
            },
            function (err) { alert('Could not get location: ' + err.message); },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });

    zoomSlider.addEventListener('input', function () {
        state.fovDeg = parseInt(zoomSlider.value, 10);
        zoomLevel.textContent = state.fovDeg + '\u00b0';
        render();
    });

    [showPlanetsCb, showEclipticCb, showGridCb, showNamesCb, showConstellationsCb]
        .forEach(function (cb) {
            if (cb) cb.addEventListener('change', render);
        });

    Array.prototype.forEach.call(dirBtns, function (btn) {
        btn.addEventListener('click', function () {
            setViewDirection(btn.getAttribute('data-dir'));
        });
    });

    infoClose.addEventListener('click', function () {
        state.selectedObject = null;
        infoPanel.classList.add('hidden');
        render();
    });

    // ------------------------------------------------------------------ boot

    /**
     * Guards the two ways this page silently died before: the CDN library 404ing
     * and calling astronomy-engine functions that do not exist. Logs failures
     * rather than throwing, so the map still renders without the ephemeris.
     */
    function selfCheck() {
        if (!Astronomy) {
            console.error('sky: astronomy-engine missing. Expected ' + ENGINE_URL);
            hideLoading('Ephemeris unavailable (astronomy-engine failed to load).', true);
            return;
        }
        try {
            var obs = new Astronomy.Observer(state.lat, state.lon, 0);
            var noon = Astronomy.MakeTime(new Date(Date.UTC(2026, 8, 24, 12, 0, 0)));
            var equ = Astronomy.Equator(Astronomy.Body.Sun, noon, obs, true, true);
            var hor = Astronomy.Horizon(noon, obs, equ.ra, equ.dec, 'normal');
            console.assert(hor.altitude > 60,
                'sky self-check: Sun should be high at local noon, got ' + hor.altitude);
            var ori = Astronomy.Constellation(5.9195, 7.4071);   // Betelgeuse
            console.assert(ori.symbol === 'Ori',
                'sky self-check: Betelgeuse should be in Ori, got ' + ori.symbol);
        } catch (err) {
            console.error('sky self-check failed:', err);
        }
    }

    function init() {
        selfCheck();
        resizeCanvas();
        state.lat = parseFloat(latInput.value) || 40.7128;
        state.lon = parseFloat(lonInput.value) || -74.0060;
        loadStars();
        loadConstellations();
        loadPlanets();
        setViewDirection('south');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
