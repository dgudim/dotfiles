// Rewrite service links to the same zone the dashboard was opened from.
// kloud.home and LAN IPs stay on *.kloud.home.
// kloud.vpn and Tailscale IPs (100.64.0.0/10) use *.kloud.vpn.
// A bare host IP is swapped the same way.
(function () {
  var LAN_HOST = "192.168.50.180";
  var VPN_HOST = "100.108.149.90";

  function isTailscale(host) {
    var parts = host.split(".").map(Number);
    if (parts.length !== 4 || parts.some(function (n) { return Number.isNaN(n); })) return false;
    return parts[0] === 100 && parts[1] >= 64 && parts[1] <= 127;
  }

  function isLan(host) {
    return host === LAN_HOST || host.startsWith("192.168.50.");
  }

  function zone() {
    var host = location.hostname;
    if (host === "kloud.vpn" || host.endsWith(".kloud.vpn") || isTailscale(host)) return "vpn";
    if (host === "kloud.home" || host.endsWith(".kloud.home") || isLan(host)) return "home";
    return "home";
  }

  function rewrite(href, z) {
    var url;
    try {
      url = new URL(href, location.origin);
    } catch (e) {
      return href;
    }
    var host = url.hostname;
    if (host.endsWith(".kloud.home") && !host.endsWith(".kloud.home.kg")) {
      var name = host.slice(0, -".kloud.home".length);
      url.hostname = name + (z === "vpn" ? ".kloud.vpn" : ".kloud.home");
      return url.toString();
    }
    if (host.endsWith(".kloud.vpn")) {
      var vpnName = host.slice(0, -".kloud.vpn".length);
      url.hostname = vpnName + (z === "vpn" ? ".kloud.vpn" : ".kloud.home");
      return url.toString();
    }
    if (host === LAN_HOST || host === VPN_HOST) {
      url.hostname = z === "vpn" ? VPN_HOST : LAN_HOST;
      return url.toString();
    }
    return href;
  }

  function apply() {
    var z = zone();
    document.querySelectorAll("a[href]").forEach(function (a) {
      var current = a.getAttribute("href");
      if (!current || current.charAt(0) === "#" || current.startsWith("/")) return;
      if (!a.dataset.origHref) a.dataset.origHref = current;
      var next = rewrite(a.dataset.origHref, z);
      if (a.getAttribute("href") !== next) a.setAttribute("href", next);
    });
  }

  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      apply();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule);
  } else {
    schedule();
  }
  new MutationObserver(schedule).observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["href"],
  });
})();
