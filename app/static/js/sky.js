'use strict';
(function() {
    'use strict';
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
    var showPlanetsCb = document.getElementById('show-planets');
    var showEclipticCb = document.getElementById('show-ecliptic');
    var showGridCb = document.getElementById('show-grid');
    var showNamesCb = document.getElementById('show-names');
    var dirBtns = document.querySelectorAll('.view-dir-btn');
    var DEG = Math.PI / 180;
    var RAD = 180 / Math.PI;
    var PIXELS_PER_DEG = 4;
    var state = {
        stars: [], planets: [],
        lat: 40.7128, lon: -74.0060,
        utcTime: new Date(),
        centerRa: 0, centerDec: 45,
        fovDeg: 180, viewDir: 'south',
        selectedObject: null, hoveredObject: null
    };

    function initTime() {
        var now = new Date();
        var y = now.getFullYear(), m = String(now.getMonth()+1).padStart(2,'0'),
            d = String(now.getDate()).padStart(2,'0'),
            h = String(now.getHours()).padStart(2,'0'),
            min = String(now.getMinutes()).padStart(2,'0');
        obsTimeInput.value = y+'-'+m+'-'+d+'T'+h+':'+min;
        state.utcTime = now;
    }
    initTime();

    function resizeCanvas() {
        var rect = canvas.parentElement.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        canvas.style.width = rect.width+'px';
        canvas.style.height = rect.height+'px';
        ctx.setTransform(dpr,0,0,dpr,0,0);
        render();
    }
    window.addEventListener('resize', resizeCanvas);

    function loadStars() {
        return fetch('/static/data/stars.json').then(function(r){return r.json();})
            .then(function(data){ state.stars = data; loadingOverlay.style.display='none'; render(); })
            .catch(function(err){ console.error('Failed to load star catalog:', err);
                loadingOverlay.innerHTML = '<p class="text-red-400">Failed to load star catalog.</p>'; });
    }

    function loadPlanets() {
        return fetch('/sky/api/planet-positions').then(function(r){return r.json();})
            .then(function(data){ if(data.ok) state.planets = data.planets; else console.warn('Planet data unavailable:', data.error); })
            .catch(function(err){ console.warn('Failed to load planet data:', err); });
    }

    function localSiderealTime(utcTime, lon) {
        var jd = Astronomy.JulianDate.fromDate(utcTime);
        var gst = Astronomy.GMST(jd);
        return (gst + lon + 360) % 360;
    }

    function computeAltAz(raDeg, decDeg, lat, lon, utcTime) {
        var lst = localSiderealTime(utcTime, lon);
        var ha = lst - raDeg;
        var latRad = lat*DEG, decRad = decDeg*DEG, haRad = ha*DEG;
        var sinAlt = Math.sin(latRad)*Math.sin(decRad)+Math.cos(latRad)*Math.cos(decRad)*Math.cos(haRad);
        var alt = Math.asin(Math.max(-1,Math.min(1,sinAlt)))*RAD;
        var cosAlt = Math.cos(Math.asin(Math.max(-1,Math.min(1,sinAlt))));
        var cosAz = (Math.sin(decRad)-Math.sin(latRad)*sinAlt)/(Math.cos(latRad)*cosAlt);
        var az = Math.acos(Math.max(-1,Math.min(1,cosAz)))*RAD;
        if(Math.sin(haRad)>0) az = 360-az;
        if(isNaN(az)) az = 0;
        return {alt:alt, az:az};
    }

    function sunPosition(utcTime) {
        try { var e = new Astronomy.Epoch(utcTime); var s = new Astronomy.Sun(e); return {ra:s.ra, dec:s.dec}; }
        catch(e){ return null; }
    }

    function moonPosition(utcTime) {
        try { var e = new Astronomy.Epoch(utcTime); var m = new Astronomy.Moon(e); return {ra:m.ra, dec:m.dec}; }
        catch(e){ return null; }
    }

    function bodyPosition(bodyId, utcTime) {
        try { var e = new Astronomy.Epoch(utcTime); var b = new Astronomy.Epicycle(bodyId, e); return {ra:b.ra, dec:b.dec}; }
        catch(e){ return null; }
    }

    function projectRaDec(ra, dec) {
        var dRa = ra - state.centerRa;
        while(dRa>180) dRa-=360; while(dRa<-180) dRa+=360;
        var dDec = dec - state.centerDec;
        var scale = PIXELS_PER_DEG*(state.fovDeg/180);
        var w = canvas.width/(window.devicePixelRatio||1);
        var h = canvas.height/(window.devicePixelRatio||1);
        return {x:w/2+dRa*scale, y:h/2-dDec*scale};
    }

    function render() {
        var w = canvas.width/(window.devicePixelRatio||1);
        var h = canvas.height/(window.devicePixelRatio||1);
        ctx.clearRect(0,0,w,h);
        var grad = ctx.createRadialGradient(w/2,h/2,0,w/2,h/2,Math.max(w,h)/2);
        grad.addColorStop(0,'#0d1117'); grad.addColorStop(1,'#000000');
        ctx.fillStyle = grad; ctx.fillRect(0,0,w,h);
        if(showGridCb.checked) drawGrid(w,h);
        if(showEclipticCb.checked) drawEcliptic(w,h);
        drawStars(w,h);
        if(showPlanetsCb.checked) drawPlanets(w,h);
        if(state.selectedObject){
            var p = projectRaDec(state.selectedObject.ra, state.selectedObject.dec);
            ctx.beginPath(); ctx.arc(p.x,p.y,8,0,2*Math.PI);
            ctx.strokeStyle='#ffffff'; ctx.lineWidth=2; ctx.stroke();
        }
        updateCenterInfo();
    }

    function drawGrid(w,h){
        ctx.strokeStyle='rgba(255,255,255,0.07)'; ctx.lineWidth=1;
        for(var ra=0; ra<360; ra+=15){
            var p=projectRaDec(ra,0);
            ctx.beginPath(); ctx.moveTo(p.x,0); ctx.lineTo(p.x,h); ctx.stroke();
        }
        for(var dec=-90; dec<=90; dec+=15){
            if(dec===90||dec===-90) continue;
            var p=projectRaDec(0,dec);
            ctx.beginPath(); ctx.moveTo(0,p.y); ctx.lineTo(w,p.y); ctx.stroke();
        }
    }

    function drawEcliptic(w,h){
        ctx.strokeStyle='rgba(255,200,100,0.3)'; ctx.lineWidth=1.5; ctx.setLineDash([4,4]);
        var first=projectRaDec(0,0);
        ctx.beginPath(); ctx.moveTo(first.x,first.y);
        for(var i=1;i<=360;i++){ var p=projectRaDec(i,0); ctx.lineTo(p.x,p.y); }
        ctx.stroke(); ctx.setLineDash([]);
    }

    function drawStars(w,h){
        var halfFov=state.fovDeg/2;
        for(var i=0;i<state.stars.length;i++){
            var star=state.stars[i], ra=star.ra, dec=star.dec, mag=star.mag;
            var dRa=ra-state.centerRa; while(dRa>180)dRa-=360; while(dRa<-180)dRa+=360;
            var dDec=dec-state.centerDec;
            if(Math.abs(dRa)>halfFov*1.1||Math.abs(dDec)>halfFov*1.1) continue;
            var p=projectRaDec(ra,dec);
            var brightness=Math.max(0,1-(mag+5)/10);
            var radius=Math.max(1,4*brightness);
            if(brightness>0.5){
                var glow=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,radius*3);
                glow.addColorStop(0,'rgba(255,255,255,'+(0.3*brightness)+')');
                glow.addColorStop(1,'rgba(255,255,255,0)');
                ctx.fillStyle=glow; ctx.beginPath(); ctx.arc(p.x,p.y,radius*3,0,2*Math.PI); ctx.fill();
            }
            ctx.fillStyle='rgba(255,255,255,'+(0.3+0.7*brightness)+')';
            ctx.beginPath(); ctx.arc(p.x,p.y,radius,0,2*Math.PI); ctx.fill();
            star._sx=p.x; star._sy=p.y; star._r=radius;
            if(showNamesCb.checked&&star.name&&brightness>0.4){
                ctx.fillStyle='rgba(255,255,255,0.8)'; ctx.font='11px sans-serif';
                ctx.fillText(star.name,p.x+radius+2,p.y+4);
            }
        }
    }

    function drawPlanets(w,h){
        var now=state.utcTime;
        var sun=sunPosition(now);
        if(sun){ var p=projectRaDec(sun.ra,sun.dec); var sp=computeAltAz(sun.ra,sun.dec,state.lat,state.lon,now);
            drawPlanetDot(p.x,p.y,'#ffcc00',6,'Sun',sp); }
        var moon=moonPosition(now);
        if(moon){ var p=projectRaDec(moon.ra,moon.dec); var mp=computeAltAz(moon.ra,moon.dec,state.lat,state.lon,now);
            drawPlanetDot(p.x,p.y,'#c0c0c0',5,'Moon',mp); }
        var planetNames=['Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune'];
        var planetColors={Mercury:'#b5b5b5',Venus:'#fff5d0',Mars:'#e74c3c',Jupiter:'#f4d03f',Saturn:'#f4d03f',Uranus:'#7fb3d8',Neptune:'#3498db'};
        for(var i=0;i<state.planets.length;i++){
            var planet=state.planets[i];
            if(planetNames.indexOf(planet.name)===-1) continue;
            var pos=bodyPosition(planet.id,now);
            if(!pos) continue;
            var p=projectRaDec(pos.ra,pos.dec);
            var bp=computeAltAz(pos.ra,pos.dec,state.lat,state.lon,now);
            var color=planetColors[planet.name]||'#ffffff';
            var radius=(planet.name==='Jupiter')?6:4;
            drawPlanetDot(p.x,p.y,color,radius,planet.name,bp);
        }
    }

    function drawPlanetDot(x,y,color,radius,name,altAz){
        var glow=ctx.createRadialGradient(x,y,0,x,y,radius*4);
        glow.addColorStop(0,color+'80'); glow.addColorStop(1,color+'00');
        ctx.fillStyle=glow; ctx.beginPath(); ctx.arc(x,y,radius*4,0,2*Math.PI); ctx.fill();
        ctx.fillStyle=color; ctx.beginPath(); ctx.arc(x,y,radius,0,2*Math.PI); ctx.fill();
        ctx.fillStyle='rgba(255,255,255,0.9)'; ctx.font='bold 12px sans-serif';
        ctx.fillText(name,x+radius+4,y+4);
    }

    function findObjectAt(x,y){
        var now=state.utcTime, best=null, bestDist=20;
        var sun=sunPosition(now);
        if(sun){ var p=projectRaDec(sun.ra,sun.dec); var dx=x-p.x,dy=y-p.y;
            if(Math.sqrt(dx*dx+dy*dy)<10){ var sa=computeAltAz(sun.ra,sun.dec,state.lat,state.lon,now);
                best={ra:sun.ra,dec:sun.dec,name:'Sun',type:'star',mag:-26.7,constellation:'—',distance:'—',elevation:sa.alt.toFixed(1)+'°'}; } }
        var moon=moonPosition(now);
        if(moon&&!best){ var p=projectRaDec(moon.ra,moon.dec); var dx=x-p.x,dy=y-p.y;
            if(Math.sqrt(dx*dx+dy*dy)<8){ var ma=computeAltAz(moon.ra,moon.dec,state.lat,state.lon,now);
                best={ra:moon.ra,dec:moon.dec,name:'Moon',type:'moon',mag:-12.7,constellation:'—',distance:'384,400 km',elevation:ma.alt.toFixed(1)+'°'}; } }
        for(var i=0;i<state.planets.length;i++){
            var planet=state.planets[i], pos=bodyPosition(planet.id,now);
            if(!pos||best) continue;
            var p=projectRaDec(pos.ra,pos.dec), dx=x-p.x,dy=y-p.y;
            if(Math.sqrt(dx*dx+dy*dy)<8){ var bp=computeAltAz(pos.ra,pos.dec,state.lat,state.lon,now);
                var distAum=planet.semi_major_au;
                var distKm=(typeof distAum==='number')?(distAum*149597870.7).toLocaleString()+' km':'—';
                best={ra:pos.ra,dec:pos.dec,name:planet.name,type:'planet',mag:'—',
                    constellation:getConstellation(pos.ra,pos.dec),distance:distKm,elevation:bp.alt.toFixed(1)+'°,_planetData:planet}; } }
        if(!best){ for(var i=0;i<state.stars.length;i++){
            var star=state.stars[i]; if(!star.name) continue;
            var dx=x-star._sx,dy=y-star._sy;
            if(Math.sqrt(dx*dx+dy*dy)<star._r+4){
                best={ra:star.ra,dec:star.dec,name:star.name,type:'star',mag:star.mag,
                    constellation:star.constellation||'—',distance:getStarDistance(star),elevation:'—'}; break; } } }
        return best;
    }

    function getConstellation(ra,dec){
        var threshold=5, best=null, bestDist=threshold;
        for(var i=0;i<state.stars.length;i++){
            var star=state.stars[i]; if(!star.constellation) continue;
            var dRa=ra-star.ra; while(dRa>180)dRa-=360; while(dRa<-180)dRa+=360;
            var dDec=dec-star.dec, dist=Math.sqrt(dRa*dRa+dDec*dDec);
            if(dist<bestDist){ bestDist=dist; best=star.constellation; } }
        return best||'—';
    }

    function getStarDistance(star){
        var known={'Sirius':'8.6 ly','Vega':'25 ly','Capella':'42 ly','Rigel':'860 ly','Procyon':'11.4 ly',
            'Betelgeuse':'640 ly','Altair':'17 ly','Aldebaran':'65 ly','Spica':'250 ly','Antares':'550 ly',
            'Fomalhaut':'25 ly','Deneb':'2600 ly','Regulus':'79 ly','Castor':'51 ly','Pollux':'34 ly',
            'Arcturus':'37 ly','Canopus':'310 ly','Achernar':'139 ly'};
        return known[star.name]||'—';
    }

    canvas.addEventListener('mousedown',function(e){
        state.dragStartX=e.clientX; state.dragStartY=e.clientY;
        state.dragStartCenterRa=state.centerRa; state.dragStartCenterDec=state.centerDec;
        var onDrag=function(e2){
            var dx=e2.clientX-state.dragStartX, dy=e2.clientY-state.dragStartY;
            var scale=PIXELS_PER_DEG*(state.fovDeg/180);
            state.centerRa=state.dragStartCenterRa+dx/scale;
            state.centerDec=state.dragStartCenterDec-dy/scale;
            state.selectedObject=null; infoPanel.classList.add('hidden'); render();
        };
        var off=function(){ window.removeEventListener('mousemove',onDrag); window.removeEventListener('mouseup',off); canvas.style.cursor='crosshair'; };
        window.addEventListener('mousemove',onDrag); window.addEventListener('mouseup',off);
        canvas.style.cursor='grabbing';
    });

    canvas.addEventListener('click',function(e){
        var rect=canvas.getBoundingClientRect(), x=e.clientX-rect.left, y=e.clientY-rect.top;
        var obj=findObjectAt(x,y);
        if(obj){ state.selectedObject=obj; showInfoPanel(obj); }
        else{ state.selectedObject=null; infoPanel.classList.add('hidden'); }
    });

    var touchStartX=0,touchStartY=0,touchStartRa=0,touchStartDec=0;
    canvas.addEventListener('touchstart',function(e){
        if(e.touches.length===1){ var t=e.touches[0]; touchStartX=t.clientX; touchStartY=t.clientY;
            touchStartRa=state.centerRa; touchStartDec=state.centerDec; } },{passive:true});
    canvas.addEventListener('touchmove',function(e){
        if(e.touches.length===1){ var t=e.touches[0]; var dx=t.clientX-touchStartX, dy=t.clientY-touchStartY;
            var scale=PIXELS_PER_DEG*(state.fovDeg/180);
            state.centerRa=touchStartRa+dx/scale; state.centerDec=touchStartDec-dy/scale;
            state.selectedObject=null; infoPanel.classList.add('hidden'); render(); } },{passive:true});

    dirBtns.forEach(function(btn){ btn.addEventListener('click',function(){ setViewDirection(btn.dataset.dir); }); });

    function setViewDirection(dir){
        state.viewDir=dir;
        dirBtns.forEach(function(b){ b.classList.remove('active','bg-blue-600','border-blue-500','text-white'); b.classList.add('bg-space-700','text-gray-300'); });
        for(var i=0;i<dirBtns.length;i++){ if(dirBtns[i].dataset.dir===dir){
            dirBtns[i].classList.add('active','bg-blue-600','border-blue-500','text-white');
            dirBtns[i].classList.remove('bg-space-700','text-gray-300'); } }
        switch(dir){
            case 'north': state.centerDec=90; state.centerRa=0; break;
            case 'south': state.centerDec=-90; state.centerRa=180; break;
            case 'east': state.centerDec=0; state.centerRa=90; break;
            case 'west': state.centerDec=0; state.centerRa=270; break;
            case 'zenith': state.centerDec=state.lat;
                state.centerRa=localSiderealTime(state.utcTime,state.lon)%360; break;
            case 'nadir': state.centerDec=-state.lat;
                state.centerRa=(localSiderealTime(state.utcTime,state.lon)+180)%360; break;
        }
        state.selectedObject=null; infoPanel.classList.add('hidden'); render();
    }

    timeSlider.addEventListener('input',function(){
        var hours=parseFloat(timeSlider.value);
        var base=new Date(state.utcTime); base.setHours(0,0,0,0);
        var newTime=new Date(base.getTime()+hours*3600000);
        state.utcTime=newTime; obsTimeInput.value=formatDT_LOCAL(newTime);
        state.selectedObject=null; infoPanel.classList.add('hidden'); render();
    });

    obsTimeInput.addEventListener('change',function(){
        if(obsTimeInput.value){ var localDate=new Date(obsTimeInput.value);
            state.utcTime=localDate; var hours=localDate.getHours()+localDate.getMinutes()/60;
            timeSlider.value=hours; state.selectedObject=null; infoPanel.classList.add('hidden'); render(); }
    });

    function formatDT_LOCAL(date){
        var y=date.getFullYear(), m=String(date.getMonth()+1).padStart(2,'0'),
            d=String(date.getDate()).padStart(2,'0'),
            h=String(date.getHours()).padStart(2,'0'),
            min=String(date.getMinutes()).padStart(2,'0');
        return y+'-'+m+'-'+d+'T'+h+':'+min;
    }

    locateBtn.addEventListener('click',function(){
        if(!navigator.geolocation){ alert('Geolocation is not supported by your browser.'); return; }
        navigator.geolocation.getCurrentPosition(
            function(pos){ state.lat=pos.coords.latitude; state.lon=pos.coords.longitude;
                latInput.value=state.lat.toFixed(4); lonInput.value=state.lon.toFixed(4);
                setViewDirection('zenith'); },
            function(err){ console.warn('Geolocation error:',err.message);
                alert('Could not get location: '+err.message); },
            {enableHighAccuracy:true,timeout:10000});
    });

    latInput.addEventListener('change',function(){ var val=parseFloat(latInput.value);
        if(!isNaN(val)&&val>=-90&&val<=90) state.lat=val; });
    lonInput.addEventListener('change',function(){ var val=parseFloat(lonInput.value);
        if(!isNaN(val)&&val>=-180&&val<=180) state.lon=val; });

    zoomSlider.addEventListener('input',function(){
        state.fovDeg=parseInt(zoomSlider.value);
        zoomLevel.textContent=state.fovDeg+'°'; render();
    });

    showPlanetsCb.addEventListener('change',render);
    showEclipticCb.addEventListener('change',render);
    showGridCb.addEventListener('change',render);
    showNamesCb.addEventListener('change',render);

    infoClose.addEventListener('click',function(){
        state.selectedObject=null; infoPanel.classList.add('hidden');
    });

    function updateCenterInfo(){
        var raHours=(state.centerRa/15)%24;
        var rah=Math.floor(raHours), ram=Math.floor((raHours-rah)*60),
            ras=Math.floor(((raHours-rah)*60-ram)*60);
        centerRah.textContent='RA: '+rah+'h '+ram+'m '+ras+'s';
        centerExt.textContent='Dec: '+state.centerDec.toFixed(2)+'°';
    }

    function showInfoPanel(obj){
        infoName.textContent=obj.name||'Unknown';
        infoType.textContent=obj.type==='planet'?'Planet':obj.type==='moon'?'Moon':obj.type==='star'?'Star':'Object';
        infoMag.textContent=(obj.mag!=='—'&&obj.mag!==null)?obj.mag:'—';
        infoConst.textContent=obj.constellation||'—';
        infoDist.textContent=obj.distance||'—';
        infoElev.textContent=obj.elevation||'—';
        infoPanel.classList.remove('hidden');
    }

    function init(){
        resizeCanvas();
        state.lat=parseFloat(latInput.value)||40.7128;
        state.lon=parseFloat(lonInput.value)||-74.0060;
        loadStars(); loadPlanets(); setViewDirection('south');
    }
    if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded',init); }
    else{ init(); }
})();

