/* © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved. */
/* Kalite Yönetim Sistemi — tablet arayüzü.
   Sunucu: bu bilgisayardaki app/sunucu.py (HTTPS). Kullanıcı adı + şifre ile giriş →
   oturum jetonu (sessionStorage; uygulama kapanınca silinir) → Authorization: Bearer.
   Düzenleme yetkisi sunucuda denetlenir; arayüz yalnız gösterir/gizler. */
"use strict";
var _YAPI = "38168058d0ded46903b0a0996107d45e";

var BOLUM_ADI = { ana: "Ana Sayfa", wps: "WPS", pqr: "PQR", std: "Standartlar", cert: "Sertifikalar" };
var SEKME_BOLUM = { 1: "wps", 2: "pqr", 3: "std", 4: "cert" };   // ozet.SEKME ile aynı indeksler
var SEVIYE_ADI = { kritik: "Kritik", uyari: "Uyarı", bilgi: "Bilgi" };
var STD_DURUM = { guncel: ["Güncel", "iyi"], guncelleme: ["Yeni sürüm var", "dikkatli"],
  manuel: ["Elle kontrol", "dikkatli"], hata: ["Kontrol hatası", "kotu"], kontrol: ["Kontrol edilmedi", ""] };
var WPS_DURUM = { "Aktif": "iyi", "Revizyon Bekliyor": "dikkatli", "İptal": "kotu" };
var PQR_TEST = { "Geçti": "iyi", "Beklemede": "dikkatli", "Başarısız": "kotu" };
var UZUN_ALANLAR = ["notlar", "title", "kapsam"];

var durum = { etiketler: null, onbellek: {}, yetki: {}, bolum: "ana", arama: {} };
var icerik = document.getElementById("icerik");

/* ── yardımcılar ─────────────────────────────────────────────── */
function el(etiket, sinif, metin) {
  var e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined && metin !== null) e.textContent = metin;
  return e;
}
// app/search_utils.tr_fold ile aynı: İ/I/ı/i eşdeğer
function trFold(s) {
  return String(s || "").replace(/[İIı]/g, "i").toLowerCase().replace(/\u0307/g, "");
}
function eslesir(sorgu, alanlar) {
  var t = trFold(sorgu).split(/\s+/).filter(Boolean);
  if (!t.length) return true;
  var yigin = alanlar.map(trFold).join(" ");
  return t.every(function (x) { return yigin.indexOf(x) >= 0; });
}
function kalanGun(bitis) {
  if (!bitis) return null;
  var b = new Date(String(bitis).slice(0, 10) + "T00:00:00");
  if (isNaN(b)) return null;
  var bugun = new Date(); bugun.setHours(0, 0, 0, 0);
  return Math.round((b - bugun) / 86400000);
}
function depo(ad, deger) {   // sessionStorage: uygulama kapanınca jeton silinir
  try {
    if (deger === undefined) return JSON.parse(sessionStorage.getItem(ad) || "null");
    if (deger === null) sessionStorage.removeItem(ad); else sessionStorage.setItem(ad, JSON.stringify(deger));
  } catch (e) { return null; }
}

/* ── sunucu ──────────────────────────────────────────────────── */
function istek(yontem, yol, govde) {
  var h = { "Accept": "application/json" };
  var j = depo("jeton");
  if (j) h["Authorization"] = "Bearer " + j;
  var s = { method: yontem, headers: h, cache: "no-store" };
  if (govde !== undefined) { h["Content-Type"] = "application/json"; s.body = JSON.stringify(govde); }
  return fetch(yol, s).then(function (r) {
    return r.json().then(function (v) { return { kod: r.status, v: v }; },
                         function () { return { kod: r.status, v: {} }; });
  }, function () { throw { tur: "ag" }; }).then(function (y) {
    if (y.kod === 401 && yol !== "/api/giris") { oturumKapandi(); throw { tur: "oturum" }; }
    if (y.kod >= 400) throw { tur: "sunucu", kod: y.kod, mesaj: y.v.hata, kalan: y.v.kalan_sn };
    return y.v;
  });
}
function getir(yol) { return istek("GET", yol); }

/* ── giriş / oturum ──────────────────────────────────────────── */
function oturumKapandi() {
  depo("jeton", null); depo("kullanici", null);
  durum.onbellek = {}; durum.etiketler = null;
  girisGoster("Oturumunuz kapandı ya da süresi doldu; yeniden giriş yapın.");
}

function girisGoster(mesaj) {
  document.body.classList.add("girissiz");
  var kutu = document.getElementById("giris");
  kutu.hidden = false;
  document.getElementById("giris-mesaj").textContent = mesaj || "";
  document.getElementById("giris-sifre").value = "";
  document.getElementById("giris-ad").focus();
}

function girisYap(e) {
  e.preventDefault();
  var dugme = document.getElementById("giris-dugme");
  var mesaj = document.getElementById("giris-mesaj");
  dugme.disabled = true; mesaj.textContent = "Giriş yapılıyor…";
  istek("POST", "/api/giris", { ad: document.getElementById("giris-ad").value,
                                sifre: document.getElementById("giris-sifre").value })
    .then(function (g) {
      depo("jeton", g.jeton); depo("kullanici", g.kullanici);
      document.getElementById("giris").hidden = true;
      document.body.classList.remove("girissiz");
      kullaniciGoster(); goster();
    }, function (h) {
      mesaj.textContent = h.tur === "ag" ? "Sunucuya ulaşılamıyor. Bilgisayarda tablet sunucusunun açık ve tabletin aynı Wi-Fi ağında olduğunu kontrol edin."
        : (h.mesaj || "Giriş yapılamadı.");
      document.getElementById("giris-sifre").value = "";
    }).then(function () { dugme.disabled = false; });
}

function cikisYap() {
  istek("POST", "/api/cikis", {}).then(null, function () {}).then(function () {
    depo("jeton", null); depo("kullanici", null);
    durum.onbellek = {}; durum.etiketler = null;
    icerik.innerHTML = "";
    girisGoster("Çıkış yapıldı.");
  });
}

function kullaniciGoster() {
  var k = depo("kullanici");
  document.getElementById("kullanici").textContent = k ? (k.ad_soyad || k.ad) + " · " + k.rol_adi : "";
}

/* ── hata / bağlantı ─────────────────────────────────────────── */
function hataGoster(h) {
  if (h && h.tur === "oturum") return;   // giriş ekranı zaten açıldı
  icerik.innerHTML = "";
  var k = el("div", "hata-kutu");
  var mesaj = {
    ag: ["Sunucuya ulaşılamıyor",
      "Bilgisayarda tablet sunucusunun açık olduğunu ve tabletin aynı Wi-Fi ağında olduğunu kontrol edin."],
    sunucu: ["Sunucu hatası", (h && h.mesaj) || ("Sunucu bir hata döndürdü (kod " + (h && h.kod) + ").")]
  }[h && h.tur] || ["Beklenmeyen hata", String(h)];
  k.appendChild(el("h2", null, mesaj[0]));
  k.appendChild(el("p", null, mesaj[1]));
  if (window.Erisim && window.Erisim.ayarlar) {
    var b = el("button", "birincil", "Bağlantı ayarları");
    b.onclick = function () { window.Erisim.ayarlar(); };
    k.appendChild(b);
  }
  icerik.appendChild(k);
  document.getElementById("baglanti").textContent = "Bağlantı yok";
}

/* ── panel ───────────────────────────────────────────────────── */
var perde = document.getElementById("perde");
function paneliAc(baslik, govde) {
  document.getElementById("panel-baslik").textContent = baslik;
  var pg = document.getElementById("panel-govde");
  pg.innerHTML = ""; pg.appendChild(govde);
  perde.hidden = false;
  document.getElementById("kapat").focus();
}
function paneliKapat() { perde.hidden = true; }
document.getElementById("kapat").onclick = paneliKapat;
perde.addEventListener("click", function (e) { if (e.target === perde) paneliKapat(); });
document.addEventListener("keydown", function (e) { if (e.key === "Escape") paneliKapat(); });

/* ── ana sayfa ───────────────────────────────────────────────── */
function olcu(ad, deger, sinif) {
  var d = el("div", "olcu");
  d.appendChild(el("span", null, ad));
  d.appendChild(el("b", sinif || "", String(deger)));
  return d;
}
function altKart(baslik, buyuk, olculer) {
  var d = el("div");
  d.appendChild(el("h4", null, baslik));
  d.appendChild(el("div", "sayi-buyuk", String(buyuk)));
  olculer.forEach(function (o) { d.appendChild(o); });
  return d;
}
function grupKart(baslik, sol, sag, dugmeler) {
  var k = el("section", "kart");
  k.appendChild(el("h3", null, baslik));
  var ic = el("div", "kart-ic"); ic.appendChild(sol); ic.appendChild(sag); k.appendChild(ic);
  dugmeler.forEach(function (d) {
    var b = el("button", "kart-ac", d[0] + "  →");
    b.onclick = function () { git(d[1]); };
    k.appendChild(b); k.appendChild(document.createTextNode(" "));
  });
  return k;
}

function anaSayfa() {
  return getir("/api/ozet").then(function (o) {
    icerik.innerHTML = "";
    var saat = new Date().getHours();
    icerik.appendChild(el("h1", null, saat < 12 ? "Günaydın" : saat < 18 ? "İyi günler" : "İyi akşamlar"));
    var k = o.kaynak, b = o.belge;
    icerik.appendChild(el("p", "alt-baslik", new Date().toLocaleDateString("tr-TR",
      { day: "numeric", month: "long", year: "numeric", weekday: "long" }) + "  •  " +
      k.wps_toplam + " WPS · " + k.pqr_toplam + " PQR · " + b.std_toplam + " standart · " +
      b.cert_toplam + " sertifika"));

    icerik.appendChild(el("h2", "bolum", "Dikkat gerektirenler"));
    var liste = el("div", "dikkat");
    if (!o.dikkat.length) liste.appendChild(el("div", "her-sey-yolunda", "✓  Bekleyen iş yok, her şey güncel."));
    o.dikkat.forEach(function (d) {
      var s = el("button", "dikkat-satir " + d.seviye);
      s.appendChild(el("span", "etiket", SEVIYE_ADI[d.seviye]));
      s.appendChild(el("span", null, d.metin));
      s.appendChild(el("span", "ok", "›"));
      s.onclick = function () { git(SEKME_BOLUM[d.sekme]); };
      liste.appendChild(s);
    });
    icerik.appendChild(liste);

    icerik.appendChild(el("h2", "bolum", "Özet"));
    var gr = el("div", "gruplar");
    gr.appendChild(grupKart("Kaynak prosedürleri",
      altKart("WPS", k.wps_toplam, [olcu("Aktif", k.wps_aktif, "iyi"),
        olcu("Revizyon bekliyor", k.wps_revizyon, k.wps_revizyon ? "dikkatli" : ""),
        olcu("İptal", k.wps_iptal), olcu("PQR'si yok", k.wps_pqrsiz, k.wps_pqrsiz ? "dikkatli" : "")]),
      altKart("PQR", k.pqr_toplam, [olcu("Geçti", k.pqr_gecti, "iyi"),
        olcu("Bekliyor", k.pqr_bekliyor, k.pqr_bekliyor ? "dikkatli" : ""),
        olcu("Başarısız", k.pqr_basarisiz, k.pqr_basarisiz ? "kotu" : ""),
        olcu("WPS'e bağlı değil", k.pqr_wpssiz)]),
      [["WPS listesi", "wps"], ["PQR listesi", "pqr"]]));
    var yakin = b.cert_en_yakin ? b.cert_en_yakin[0] + " (" + b.cert_en_yakin[1] + " gün)" : "—";
    gr.appendChild(grupKart("Belge takibi",
      altKart("Standartlar", b.std_toplam, [olcu("Güncel", b.std_guncel, "iyi"),
        olcu("Yeni sürüm var", b.std_guncelleme, b.std_guncelleme ? "dikkatli" : ""),
        olcu("Elle kontrol bekliyor", b.std_kontrol), olcu("Son kontrol", b.std_son_kontrol || "—")]),
      altKart("Sertifikalar", b.cert_toplam, [olcu("Geçerli", b.cert_gecerli, "iyi"),
        olcu("Yakında dolacak", b.cert_yakinda, b.cert_yakinda ? "dikkatli" : ""),
        olcu("Süresi dolmuş", b.cert_dolmus, b.cert_dolmus ? "kotu" : ""), olcu("En yakın", yakin)]),
      [["Standartlar", "std"], ["Sertifikalar", "cert"]]));
    icerik.appendChild(gr);
  });
}

/* ── listeler ────────────────────────────────────────────────── */
function rozet(bolum, k) {
  if (bolum === "wps") return [k.durum || "—", WPS_DURUM[k.durum] || ""];
  if (bolum === "pqr") return [k.test || "—", PQR_TEST[k.test] || ""];
  if (bolum === "std") return STD_DURUM[k.status] || STD_DURUM.kontrol;
  var kalan = kalanGun(k.bitis);
  if (kalan === null) return ["Tarihsiz", ""];
  if (kalan < 0) return ["Süresi dolmuş", "kotu"];
  if (kalan <= durum.etiketler.uyari_gun) return [kalan + " gün kaldı", "dikkatli"];
  return ["Geçerli", "iyi"];
}
function ozetMetni(bolum, k) {
  var p = { wps: [k.proses, k.metal, k.dolgu, k.pqr && "PQR: " + k.pqr],
    pqr: [k.proses, k.metal, k.dolgu, k.lab],
    std: [k.title, k.org, k.myVer && "Sürüm: " + k.myVer],
    cert: [k.ad, k.org, k.bitis && "Bitiş: " + k.bitis] }[bolum];
  return p.filter(Boolean).join("  ·  ");
}
function aramaAlanlari(bolum, k) {
  return [k.no, ozetMetni(bolum, k), k.durum, k.test, k.kapsam, k.folder_no];
}

function listeYukle(bolum) {
  if (durum.onbellek[bolum]) return Promise.resolve(durum.onbellek[bolum]);
  return getir("/api/" + bolum).then(function (r) {
    durum.onbellek[bolum] = r.kayitlar; durum.yetki[bolum] = r.duzenleyebilir;
    return r.kayitlar;
  });
}

function listeSayfasi(bolum) {
  return listeYukle(bolum).then(function (kayitlar) {
    icerik.innerHTML = "";
    icerik.appendChild(el("h1", null, BOLUM_ADI[bolum]));
    var cubuk = el("div", "arac-cubugu");
    var ara = el("input", "arama"); ara.type = "search";
    ara.placeholder = "Ara (no, başlık, kuruluş, proses...)"; ara.value = durum.arama[bolum] || "";
    var adet = el("span", "adet");
    cubuk.appendChild(ara); cubuk.appendChild(adet);
    if (durum.yetki[bolum]) {
      var yeni = el("button", "birincil", "+  Yeni kayıt");
      yeni.onclick = function () { formAc(bolum, null); };
      cubuk.appendChild(yeni);
    }
    icerik.appendChild(cubuk);
    var liste = el("div", "liste");
    icerik.appendChild(liste);

    function ciz() {
      var q = ara.value; durum.arama[bolum] = q;
      var sonuc = kayitlar.filter(function (k) { return eslesir(q, aramaAlanlari(bolum, k)); });
      adet.textContent = sonuc.length + " / " + kayitlar.length + " kayıt";
      var parca = document.createDocumentFragment();
      sonuc.forEach(function (k) {
        var s = el("button", "kayit");
        s.appendChild(el("span", "no", k.no || "—"));
        s.appendChild(el("span", "ozet", ozetMetni(bolum, k)));
        var r = rozet(bolum, k);
        s.appendChild(el("span", "rozet " + r[1], r[0]));
        s.onclick = function () { detay(bolum, k); };
        parca.appendChild(s);
      });
      liste.innerHTML = ""; liste.appendChild(parca);
    }
    var zaman;
    ara.addEventListener("input", function () { clearTimeout(zaman); zaman = setTimeout(ciz, 120); });
    ciz();
  });
}

function degerYaz(dd, v) {
  if (Array.isArray(v)) {
    if (!v.length) { dd.textContent = "—"; return; }
    v.forEach(function (x) {
      dd.appendChild(el("div", null, typeof x === "object" && x !== null
        ? Object.keys(x).filter(function (a) { return x[a] !== "" && x[a] !== null; })
            .map(function (a) { return a + ": " + x[a]; }).join(" · ")
        : String(x)));
    });
  } else if (typeof v === "object" && v !== null) {
    dd.textContent = Object.keys(v).map(function (a) { return a + ": " + v[a]; }).join("\n");
  } else {
    dd.textContent = String(v);
  }
}
function detay(bolum, k) {
  var g = el("div");
  if (durum.yetki[bolum]) {
    var islem = el("div", "islem-cubugu");
    var duz = el("button", "birincil", "Düzenle");
    duz.onclick = function () { formAc(bolum, k); };
    var sil = el("button", "tehlike", "Sil");
    sil.onclick = function () { kayitSil(bolum, k); };
    islem.appendChild(duz); islem.appendChild(sil);
    g.appendChild(islem);
  }
  var dl = el("dl");
  var etiket = durum.etiketler.detay;
  var r = rozet(bolum, k);
  var ust = el("div", "alan");
  ust.appendChild(el("dt", null, "Durum")); var dd0 = el("dd"); dd0.appendChild(el("span", "rozet " + r[1], r[0]));
  ust.appendChild(dd0); dl.appendChild(ust);
  Object.keys(k).forEach(function (a) {
    var v = k[a];
    if (a.charAt(0) === "_" || v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length)) return;
    var satir = el("div", "alan");
    satir.appendChild(el("dt", null, etiket[a] || a));
    var dd = el("dd"); degerYaz(dd, v); satir.appendChild(dd);
    dl.appendChild(satir);
  });
  g.appendChild(dl);
  paneliAc((k.no || "Kayıt") + (k.rev ? "  Rev. " + k.rev : ""), g);
}

/* ── düzenleme formu ─────────────────────────────────────────── */
function formAlanlari(bolum, k) {
  // tablo sütunları (masaüstüyle aynı) + kaydın diğer düz metin alanları; iç içe veri
  // (paso tabloları vb.) formda gösterilmez ama kayıtta korunur
  var alanlar = [];
  durum.etiketler.sutunlar[bolum].forEach(function (s) {
    if (s[1].charAt(0) !== "_" && alanlar.indexOf(s[1]) < 0) alanlar.push(s[1]);
  });
  Object.keys(k || {}).forEach(function (a) {
    var v = k[a];
    if (a.charAt(0) !== "_" && alanlar.indexOf(a) < 0 && (typeof v === "string" || typeof v === "number"))
      alanlar.push(a);
  });
  if (alanlar.indexOf("notlar") < 0) alanlar.push("notlar");
  return alanlar;
}

function formAc(bolum, k, girilen) {   // girilen: 409 sonrası kullanıcının değiştirdiği alanlar
  var form = el("form", "duzen-formu");
  form.noValidate = true;
  var girdiler = {}, ilkler = {};
  formAlanlari(bolum, k).forEach(function (a) {
    var etiket = el("label", "form-alan");
    etiket.appendChild(el("span", null, durum.etiketler.detay[a] || a));
    var sec = durum.etiketler.secenekler[bolum + "." + a];
    var deger = k && k[a] !== undefined && k[a] !== null ? String(k[a]) : "";
    var g;
    if (sec) {
      g = el("select");
      g.appendChild(el("option", null, "—")).value = "";
      sec.forEach(function (s) { var o = el("option", null, s[1]); o.value = s[0]; g.appendChild(o); });
      if (deger && !sec.some(function (s) { return s[0] === deger; })) {
        var o = el("option", null, deger); o.value = deger; g.appendChild(o);   // listede yoksa koru
      }
      g.value = deger;
    } else if (UZUN_ALANLAR.indexOf(a) >= 0) {
      g = el("textarea"); g.rows = 3; g.value = deger;
    } else {
      g = el("input");
      g.type = durum.etiketler.tarih_alanlari.indexOf(a) >= 0 && (!deger || /^\d{4}-\d{2}-\d{2}$/.test(deger)) ? "date" : "text";
      g.value = deger;
    }
    if (a === "no") g.required = true;
    etiket.appendChild(g); form.appendChild(etiket);
    girdiler[a] = g;
    // fark tarayıcının gösterdiği değere göre (textarea \r\n → \n vb.): aksi halde dokunulmamış
    // alan "değişti" sayılıp öbür cihazın değişikliğini ezerdi
    ilkler[a] = g.value;
    if (girilen && girilen[a] !== undefined) {
      if (sec && !Array.prototype.some.call(g.options, function (o) { return o.value === girilen[a]; })) {
        var eklenen = el("option", null, girilen[a]); eklenen.value = girilen[a]; g.appendChild(eklenen);
      }
      g.value = girilen[a];
    }
  });
  var mesaj = el("p", "form-mesaj");
  form.appendChild(mesaj);
  var kaydet = el("button", "birincil", k ? "Kaydet" : "Ekle");
  kaydet.type = "submit";
  form.appendChild(kaydet);
  form.onsubmit = function (e) {
    e.preventDefault();
    var veri = {};
    Object.keys(k || {}).forEach(function (a) { if (a.charAt(0) !== "_") veri[a] = k[a]; });   // iç içe alanlar korunur
    Object.keys(girdiler).forEach(function (a) { veri[a] = girdiler[a].value.trim(); });
    if (!veri.no) { mesaj.textContent = "No alanı boş olamaz."; girdiler.no.focus(); return; }
    kaydet.disabled = true; mesaj.textContent = "Kaydediliyor…";
    var p = k ? istek("PUT", "/api/" + bolum + "/" + k._id, { veri: veri, surum: k._surum })
              : istek("POST", "/api/" + bolum, { veri: veri });
    p.then(function () {
      paneliKapat(); durum.onbellek[bolum] = null; goster();
    }, function (h) {
      kaydet.disabled = false;
      if (h.tur === "oturum") return;
      if (h.kod === 409 && k) {
        // Eski sürümle yazılmaz: güncel kayıt yüklenir, yalnız kullanıcının değiştirdiği alanlar
        // forma taşınır (öbür cihazın değişikliği ezilmez, yazılanlar kaybolmaz; BULGU-13)
        var girilen = {};
        Object.keys(girdiler).forEach(function (a) {
          if (girdiler[a].value !== ilkler[a]) girilen[a] = girdiler[a].value;
        });
        durum.onbellek[bolum] = null;
        listeYukle(bolum).then(function (liste) {
          var guncel = liste.filter(function (x) { return x._id === k._id; })[0];
          goster();
          if (!guncel) {
            paneliKapat();
            window.alert("Kayıt başka cihazda silinmiş; değişiklikleriniz kaydedilmedi.");
            return;
          }
          formAc(bolum, guncel, girilen);
          window.alert((h.mesaj || "Kayıt başka cihazda değiştirildi.") +
            " Güncel kayıt yüklendi; değiştirdiğiniz alanlar korundu. Kontrol edip yeniden kaydedin.");
        }, function () {
          mesaj.textContent = "Güncel kayıt alınamadı; bağlantıyı kontrol edip yeniden deneyin.";
        });
        return;
      }
      mesaj.textContent = h.tur === "ag" ? "Sunucuya ulaşılamıyor; değişiklik kaydedilmedi." : (h.mesaj || "Kaydedilemedi.");
    });
  };
  paneliAc(k ? (k.no + " — düzenle") : (BOLUM_ADI[bolum] + " — yeni kayıt"), form);
  var ilk = girdiler.no; if (ilk) ilk.focus();
}

function kayitSil(bolum, k) {
  if (!window.confirm((k.no || "Bu kayıt") + " silinsin mi? Bu işlem geri alınamaz (değişiklik kaydında kalır).")) return;
  istek("DELETE", "/api/" + bolum + "/" + k._id + "?surum=" + k._surum).then(function () {
    paneliKapat(); durum.onbellek[bolum] = null; goster();
  }, function (h) {
    if (h.tur === "oturum") return;
    window.alert(h.mesaj || "Silinemedi.");
    durum.onbellek[bolum] = null; goster();
  });
}

/* ── gezinme ─────────────────────────────────────────────────── */
function git(bolum) { location.hash = "#" + bolum; }
function goster() {
  if (!depo("jeton")) { girisGoster(); return; }
  var bolum = (location.hash || "#ana").slice(1);
  if (!BOLUM_ADI[bolum]) bolum = "ana";
  durum.bolum = bolum;
  Array.prototype.forEach.call(document.querySelectorAll(".menu-dugme[data-bolum]"), function (b) {
    if (b.getAttribute("data-bolum") === bolum) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  paneliKapat();
  icerik.innerHTML = ""; icerik.appendChild(el("div", "yukleniyor", "Yükleniyor…"));
  var hazir = durum.etiketler ? Promise.resolve()
    : getir("/api/etiketler").then(function (e) { durum.etiketler = e; });
  hazir.then(function () { return bolum === "ana" ? anaSayfa() : listeSayfasi(bolum); })
    .then(function () {
      document.getElementById("baglanti").textContent = "Bağlı: " + location.host + "  ·  " +
        new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
      icerik.scrollTop = 0;
    }, hataGoster);
}
// Sayfanın tamamı yeniden yüklenir: veri + güncellenmiş arayüz dosyaları (sunucu no-store)
function yenile() { location.reload(); }

Array.prototype.forEach.call(document.querySelectorAll(".menu-dugme[data-bolum]"), function (b) {
  b.onclick = function () { git(b.getAttribute("data-bolum")); };
});
document.getElementById("yenile").onclick = yenile;
document.getElementById("cikis").onclick = cikisYap;
document.getElementById("ayarlar").onclick = function () {
  if (window.Erisim && window.Erisim.ayarlar) window.Erisim.ayarlar();
};
if (!(window.Erisim && window.Erisim.ayarlar)) document.getElementById("ayarlar").hidden = true;
document.getElementById("giris-formu").onsubmit = girisYap;
window.addEventListener("hashchange", goster);
kullaniciGoster();
goster();
