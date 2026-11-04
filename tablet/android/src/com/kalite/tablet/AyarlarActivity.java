/* © 2026 Umut Can Hocaoğlu. Tüm hakları saklıdır / All rights reserved. */
package com.kalite.tablet;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Sunucu adresi (yalnız https; bilgisayardaki sunucu penceresinde yazar). Kullanıcı adı ve
 *  şifre burada değil, web arayüzünde girilir; APK sır saklamaz. */
public class AyarlarActivity extends Activity {
    private EditText adres;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        SharedPreferences t = getSharedPreferences(MainActivity.TERCIH, MODE_PRIVATE);
        int d = (int) (getResources().getDisplayMetrics().density * 16);

        LinearLayout k = new LinearLayout(this);
        k.setOrientation(LinearLayout.VERTICAL);
        k.setPadding(d * 3, d * 3, d * 3, d * 3);
        k.setBackgroundColor(Color.parseColor("#0b1220"));

        k.addView(yazi("Bağlantı ayarları", 30, true));
        k.addView(yazi("Bilgisayarda \"Tablet Sunucusu\" penceresinde yazan https:// adresini "
            + "girin. Tablet ile bilgisayar aynı Wi-Fi ağında olmalı. Giriş, kendi kullanıcı adınız "
            + "ve şifrenizle bir sonraki ekranda yapılır.", 18, false));
        k.addView(yazi("Sunucu adresi", 18, true));
        String eski = t.getString("sunucu", "https://192.168.1.23:8765");
        adres = alan(eski.replace("http://", "https://"), InputType.TYPE_TEXT_VARIATION_URI);
        k.addView(adres);

        Button kaydet = new Button(this);
        kaydet.setText("Kaydet ve bağlan");
        kaydet.setTextSize(20);
        kaydet.setAllCaps(false);
        kaydet.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { kaydet(); }
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = d * 2;
        k.addView(kaydet, lp);

        ScrollView sv = new ScrollView(this);
        sv.addView(k);
        setContentView(sv);
    }

    private TextView yazi(String s, int boy, boolean kalin) {
        TextView v = new TextView(this);
        v.setText(s);
        v.setTextSize(boy);
        v.setTextColor(kalin ? Color.WHITE : Color.parseColor("#94a3b8"));
        if (kalin) v.setTypeface(null, android.graphics.Typeface.BOLD);
        v.setPadding(0, 24, 0, 8);
        return v;
    }

    private EditText alan(String deger, int tur) {
        EditText e = new EditText(this);
        e.setText(deger);
        e.setTextSize(20);
        e.setSingleLine(true);
        e.setInputType(InputType.TYPE_CLASS_TEXT | tur);
        e.setTextColor(Color.WHITE);
        e.setGravity(Gravity.CENTER_VERTICAL);
        return e;
    }

    @Override
    public void onBackPressed() {
        // Hiç ayar kaydedilmeden geri: ana ekran ayarları tekrar açardı; uygulamadan çık
        if (!getSharedPreferences(MainActivity.TERCIH, MODE_PRIVATE).getString("sunucu", "")
                .startsWith("https://"))
            finishAffinity();
        else
            super.onBackPressed();
    }

    private void kaydet() {
        String a = adres.getText().toString().trim();
        while (a.endsWith("/")) a = a.substring(0, a.length() - 1);
        if (a.startsWith("http://")) {
            Toast.makeText(this, "Yalnız şifreli bağlantı (https://) kabul edilir", Toast.LENGTH_LONG).show();
            return;
        }
        if (!a.startsWith("https://")) a = "https://" + a;
        getSharedPreferences(MainActivity.TERCIH, MODE_PRIVATE).edit()
            .putString("sunucu", a).remove("anahtar").apply();   // eski sürümün anahtarını sil
        finish();
    }
}
