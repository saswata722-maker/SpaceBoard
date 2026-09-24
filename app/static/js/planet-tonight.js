/* SpaceBoard — "Where to find this planet tonight".
 *
 * Fills the `.planet-tonight` block on each solar system planet card with the
 * planet's current altitude/azimuth, constellation, distance and rise/set
 * times, computed in the browser with astronomy-engine.
 *
 * The library is loaded by planets.html. Every failure path (library missing,
 * geolocation denied, unsupported body, engine error) degrades to a short text
 * message instead of throwing, matching the app's "never crash the page" rule.
 */
'use strict';
(function () {

    // astronomy-engine must be loaded by the host page before this file.
    var Astronomy = window.Astronomy;
    var ENGINE_URL = 'https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js';

    // Bodies the engine can compute. Keyed by the English name used in the UI.
    var BODIES = {
        mercury: 'Mercury', venus: 'Venus', mars: 'Mars', jupiter: 'Jupiter',
        saturn: 'Saturn', uranus: 'Uranus', neptune: 'Neptune', pluto: 'Pluto'
    };

    // Used until (or unless) the browser grants geolocation access.
    var FALLBACK = { latitude: 40.7128, longitude: -74.0060, label: 'New York' };

    var COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                   'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

    function compassPoint(azimuth) {
        var i = Math.round((((azimuth % 360) + 360) % 360) / 22.5) % 16;
        return COMPASS[i];
    }

    function clockTime(date) {
        if (!date) return null;
        return String(date.getHours()).padStart(2, '0') + ':' +
               String(date.getMinutes()).padStart(2, '0');
    }

    function bodyFor(name) {
        if (!name) return null;
        var key = String(name).trim().toLowerCase();
        return BODIES[key] ? Astronomy.Body[BODIES[key]] : null;
    }

    /** Shape the numbers for one body, or throw if the engine rejects it. */
    function tonight(body, observer, when) {
        // Of-date coordinates are what Horizon() expects (RA in sidereal hours).
        var ofDate = Astronomy.Equator(body, when, observer, true, true);
        var hor = Astronomy.Horizon(when, observer, ofDate.ra, ofDate.dec, 'normal');

        // Constellation lookup needs J2000 coordinates.
        var j2000 = Astronomy.Equator(body, when, observer, false, true);
        var constellation = Astronomy.Constellation(j2000.ra, j2000.dec);

        var rise = Astronomy.SearchRiseSet(body, observer, +1, when, 1);
        var set = Astronomy.SearchRiseSet(body, observer, -1, when, 1);

        return {
            altitude: hor.altitude,
            azimuth: hor.azimuth,
            constellation: constellation.name,
            symbol: constellation.symbol,
            distance: ofDate.dist,
            rise: rise ? rise.date : null,
            set: set ? set.date : null
        };
    }

    function render(el, observer, when) {
        var name = el.getAttribute('data-planet');

        if (name && name.toLowerCase() === 'earth') {
            el.textContent = 'You are here — Earth is the observing platform.';
            return;
        }
        if (!Astronomy) {
            el.textContent = 'Sky position unavailable (astronomy engine did not load).';
            return;
        }
        var body = bodyFor(name);
        if (!body) {
            el.textContent = 'Sky position unavailable for this body.';
            return;
        }

        var info;
        try {
            info = tonight(body, observer, when);
        } catch (err) {
            el.textContent = 'Sky position unavailable.';
            return;
        }

        var visible = info.altitude > 0;
        var rows = [
            ['Altitude', info.altitude.toFixed(1) + '\u00b0' + (visible ? '' : ' (below horizon)')],
            ['Direction', visible ? compassPoint(info.azimuth) + ' (' + info.azimuth.toFixed(0) + '\u00b0)' : '\u2014'],
            ['Constellation', info.constellation + ' (' + info.symbol + ')'],
            ['Distance', info.distance.toFixed(2) + ' AU'],
            ['Rises / sets', (clockTime(info.rise) || '\u2014') + ' / ' + (clockTime(info.set) || '\u2014')]
        ];

        var dl = document.createElement('dl');
        dl.className = 'space-y-1';
        rows.forEach(function (row) {
            var wrap = document.createElement('div');
            wrap.className = 'flex justify-between gap-2';
            var dt = document.createElement('dt');
            dt.className = 'text-gray-500';
            dt.textContent = row[0];
            var dd = document.createElement('dd');
            dd.className = 'text-right ' + (visible ? 'text-gray-200' : 'text-gray-400');
            dd.textContent = row[1];
            wrap.appendChild(dt);
            wrap.appendChild(dd);
            dl.appendChild(wrap);
        });

        el.innerHTML = '';
        el.appendChild(dl);
    }

    function renderAll(observer) {
        var when = Astronomy ? Astronomy.MakeTime(new Date()) : null;
        var cards = document.querySelectorAll('.planet-tonight');
        Array.prototype.forEach.call(cards, function (el) {
            render(el, observer, when);
        });
    }

    /**
     * Guards the two failure modes that silently kill this feature: the CDN
     * library not loading, and using the wrong astronomy-engine API. Runs once;
     * failures are logged, never thrown.
     */
    function selfCheck() {
        if (!Astronomy) {
            console.error('planet-tonight: astronomy-engine missing. Expected ' + ENGINE_URL);
            return;
        }
        try {
            var observer = new Astronomy.Observer(0, 0, 0);
            var noon = Astronomy.MakeTime(new Date(Date.UTC(2026, 8, 24, 12, 0, 0)));
            var eq = Astronomy.Equator(Astronomy.Body.Sun, noon, observer, true, true);
            var hor = Astronomy.Horizon(noon, observer, eq.ra, eq.dec, 'normal');
            console.assert(hor.altitude > 60,
                'planet-tonight self-check: Sun should be high at local noon, got ' + hor.altitude);
        } catch (err) {
            console.error('planet-tonight self-check failed:', err);
        }
    }

    function init() {
        selfCheck();

        // Render with a sensible default, then refine if the browser hands us
        // the real location.
        renderAll(FALLBACK);

        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                renderAll(new Astronomy.Observer(
                    pos.coords.latitude, pos.coords.longitude, 0));
            },
            function () { /* keep the fallback */ },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
        );
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
