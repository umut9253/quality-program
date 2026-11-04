/* © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved. */
package com.kalite.tablet;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.net.http.SslCertificate;
import android.net.http.SslError;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.security.MessageDigest;

/** Bilgisayardaki tablet sunucusunun arayüzünü tam ekran gösterir (QUALITY PROGRAM/app/sunucu.py).
 *  Bağlantı yalnız HTTPS; sunucunun kendinden imzalı sertifikası parmak iziyle sabitlenir
 *  (Pin.SHA256, derlemede data/tls/sunucu.crt'den üretilir): başka sertifika = bağlantı kesilir.
 *  Kimlik doğrulama web arayüzünde (kullanıcı adı + şifre); APK sır saklamaz. */
public class MainActivity extends Activity {
    static final String TERCIH = "baglanti";
    private WebView web;
    private String sunucu;
    private boolean hataEkrani;   // hata sayfası açık: ayarlardan aynı adresle dönülünce de yükle

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setCacheMode(WebSettings.LOAD_NO_CACHE);
        ws.setAllowFileAccess(false);
        ws.setSaveFormData(false);
        web.addJavascriptInterface(new Kopru(), "Erisim");
        // WebChromeClient yoksa confirm/alert sessizce iptal edilir (Sil onayı çalışmaz)
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return !ayniKaynak(r.getUrl());   // başka siteye gitme
            }

            @Override
            public void onReceivedSslError(WebView v, SslErrorHandler h, SslError e) {
                // Kendinden imzalı sertifika: zincir yerine parmak izine güven (sabitleme)
                String url = e.getUrl();   // bazı alt kaynak hatalarında null olabilir
                if (url != null && ayniKaynak(Uri.parse(url)) && sabitMi(e.getCertificate())) {
                    h.proceed();
                } else {
                    h.cancel();
                    hataSayfasi("Sunucu sertifikası doğrulanamadı. Bu tablet yalnızca kendi "
                        + "sunucunuzun sertifikasına güvenir; sertifika yenilendiyse güncel APK'yı kurun.");
                }
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) hataSayfasi(String.valueOf(e.getDescription()));
            }
        });
        setContentView(web);
    }

    @Override
    protected void onResume() {
        super.onResume();
        SharedPreferences t = getSharedPreferences(TERCIH, MODE_PRIVATE);
        String yeni = t.getString("sunucu", "");
        if (!yeni.startsWith("https://")) {   // ilk açılış ya da eski (http) ayar
            startActivity(new Intent(this, AyarlarActivity.class));
            return;
        }
        if (!yeni.equals(sunucu) || hataEkrani) {
            sunucu = yeni;
            hataEkrani = false;
            web.loadUrl(sunucu + "/");
        }
    }

    private boolean ayniKaynak(Uri u) {
        Uri s = Uri.parse(sunucu);
        return u.getHost() != null && u.getHost().equals(s.getHost()) && u.getPort() == s.getPort()
            && "https".equalsIgnoreCase(u.getScheme());
    }

    static boolean sabitMi(SslCertificate sert) {
        try {
            byte[] der = SslCertificate.saveState(sert).getByteArray("x509-certificate");
            if (der == null) return false;
            byte[] o = MessageDigest.getInstance("SHA-256").digest(der);
            StringBuilder sb = new StringBuilder();
            for (byte x : o) sb.append(String.format("%02x", x));
            return MessageDigest.isEqual(sb.toString().getBytes("US-ASCII"),
                                         Pin.SHA256.getBytes("US-ASCII"));
        } catch (Exception ex) {
            return false;
        }
    }

    private void hataSayfasi(String neden) {
        hataEkrani = true;
        String html = "<html><head><meta name='viewport' content='width=device-width'><style>"
            + "body{font:18px sans-serif;background:#0b1220;color:#e6ebf5;padding:48px}"
            + "h1{color:#ef4444}button{font:inherit;padding:14px 22px;margin:8px 8px 0 0;border:0;"
            + "border-radius:12px;background:#3b82f6;color:#fff}</style></head><body>"
            + "<h1>Sunucuya bağlanılamıyor</h1><p>Adres: " + escape(sunucu) + "</p><p>"
            + escape(neden) + "</p><p>Bilgisayarda tablet sunucusunun açık olduğunu ve tabletin "
            + "aynı Wi-Fi ağında olduğunu kontrol edin.</p>"
            + "<button onclick='Erisim.tekrarDene()'>Tekrar dene</button>"
            + "<button onclick='Erisim.ayarlar()'>Bağlantı ayarları</button></body></html>";
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
    }

    private static String escape(String s) {
        return s == null ? "" : s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    class Kopru {
        @JavascriptInterface
        public void ayarlar() {
            startActivity(new Intent(MainActivity.this, AyarlarActivity.class));
        }

        @JavascriptInterface
        public void tekrarDene() {
            web.post(new Runnable() {
                public void run() { hataEkrani = false; web.loadUrl(sunucu + "/"); }
            });
        }
    }
}
