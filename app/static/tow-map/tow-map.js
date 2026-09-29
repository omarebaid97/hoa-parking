(function () {
  "use strict";

  var container = document.getElementById("tow-map");
  if (!container) {
    return;
  }

  // Paths adapted from the original bayoulandinghoa.com public-site copy
  // (relative "assets/..." paths) to this app's /static mount point.
  var GEOJSON_URL = "/static/tow-map/tow-zones.geojson";
  var BASE_IMG = "/static/tow-map/img/tow-base.jpg";
  var STATIC_IMG = "/static/tow-map/img/tow-map-static.png";
  var STATIC_ALT =
    "Map of Bayou Landing towing zones: orange patrolled main stretch of Ann St that connects both gates; green unpatrolled streets in front of homes";

  // Pixel size of assets/img/tow-base.jpg. The geojson is authored in the
  // same image-pixel space, as [x, -y] with origin at the image's top-left.
  var IMG_W = 1400;
  var IMG_H = 988;

  var ZONE_COLORS = {
    orange: "#f28c28",
    green: "#2e9e44"
  };

  var fellBack = false;

  function showFallback() {
    if (fellBack) {
      return;
    }
    fellBack = true;
    container.innerHTML =
      '<p class="tow-map-fallback"><img src="' +
      STATIC_IMG +
      '" alt="' +
      STATIC_ALT +
      '"></p>';
  }

  // Guard: if Leaflet itself failed to load, bail to the static image.
  if (typeof L === "undefined") {
    showFallback();
    return;
  }

  // Image-pixel [x, y] (y down, as drawn on tow-base.jpg) -> Leaflet LatLng
  // for CRS.Simple, matching the geojson's [x, -y] convention.
  function pxToLatLng(x, y) {
    return L.latLng(-y, x);
  }

  var bounds = [pxToLatLng(0, IMG_H), pxToLatLng(IMG_W, 0)]; // [south-west, north-east]

  var map;
  try {
    map = L.map(container, {
      crs: L.CRS.Simple,
      scrollWheelZoom: false,
      zoomSnap: 0.25,
      minZoom: -2,
      maxZoom: 3
    });
  } catch (err) {
    showFallback();
    return;
  }

  // Click-to-enable scroll zoom so page scrolling isn't hijacked on mobile.
  container.addEventListener("click", function () {
    map.scrollWheelZoom.enable();
  });
  map.on("blur", function () {
    map.scrollWheelZoom.disable();
  });

  var baseOverlay = L.imageOverlay(BASE_IMG, bounds, {
    attribution: "Base image: HOA towing policy map (aerial &copy; Google)"
  });

  var baseLoadFailed = false;
  baseOverlay.on("error", function () {
    baseLoadFailed = true;
    showFallback();
  });

  baseOverlay.addTo(map);
  map.fitBounds(bounds);
  map.setMaxBounds([
    pxToLatLng(-60, IMG_H + 60),
    pxToLatLng(IMG_W + 60, -60)
  ]);

  var gateIcon = L.divIcon({
    className: "tow-map-gate-icon",
    html:
      '<svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">' +
      '<circle cx="11" cy="11" r="8" fill="#2b6cb0" stroke="#fff" stroke-width="2"/>' +
      "</svg>",
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  function styleForZone(feature) {
    var zone = feature.properties && feature.properties.zone;
    var color = ZONE_COLORS[zone] || "#888";
    return {
      color: "#ffffff",
      weight: 1.5,
      opacity: 0.9,
      fillColor: color,
      fillOpacity: 0.55
    };
  }

  function onEachFeature(feature, layer) {
    var props = feature.properties || {};

    if (props.kind === "gate") {
      layer.bindPopup(props.title || "Gate");
      return;
    }

    if (props.title || props.rules) {
      var html = "";
      if (props.title) {
        html += "<strong>" + props.title + "</strong>";
      }
      if (props.rules) {
        html += "<p>" + props.rules + "</p>";
      }
      layer.bindPopup(html);
    }

    if (layer.setStyle) {
      layer.on("mouseover", function () {
        layer.setStyle({ weight: 3, fillOpacity: 0.7 });
      });
      layer.on("mouseout", function () {
        layer.setStyle(styleForZone(feature));
      });
    }
  }

  function pointToLayer(feature, latlng) {
    return L.marker(latlng, { icon: gateIcon });
  }

  // geojson coordinates are already [x, -y] i.e. [lng, lat] in the same
  // convention pxToLatLng uses, so Leaflet's default coordsToLatLng works.
  fetch(GEOJSON_URL)
    .then(function (res) {
      if (!res.ok) {
        throw new Error("HTTP " + res.status);
      }
      return res.json();
    })
    .then(function (data) {
      L.geoJSON(data, {
        style: styleForZone,
        pointToLayer: pointToLayer,
        onEachFeature: onEachFeature
      }).addTo(map);

      addLegend();
    })
    .catch(function () {
      showFallback();
    });

  function addLegend() {
    var legend = L.control({ position: "bottomleft" });
    legend.onAdd = function () {
      var div = L.DomUtil.create("div", "tow-map-legend");
      div.innerHTML =
        '<h4>Where can I park?</h4>' +
        '<div class="tow-map-legend-row">' +
        '<span class="tow-map-legend-swatch" style="background:' +
        ZONE_COLORS.orange +
        '"></span> Orange: patrolled, permit required</div>' +
        '<div class="tow-map-legend-row">' +
        '<span class="tow-map-legend-swatch" style="background:' +
        ZONE_COLORS.green +
        '"></span> Green: not patrolled, towed only if you block a resident</div>';
      L.DomEvent.disableClickPropagation(div);
      return div;
    };
    legend.addTo(map);
  }
})();
