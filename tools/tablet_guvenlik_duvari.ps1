# Tablet sunucusu için Windows Güvenlik Duvarı izni (YÖNETİCİ olarak bir kez çalıştırılır).
#
# Ne yapar: yalnız "Özel" ağ profilinde, yalnız bu Python'a ve yalnız TCP 8765'e gelen
# bağlantıya izin verir. "Genel" (kafe, otel vb.) ağlarda sunucu yine kapalı kalır.
# Ön koşul: ev/iş Wi-Fi'ı "Özel ağ" olmalı (Ayarlar > Ağ ve İnternet > Wi-Fi >
# ağ adı > Ağ profili türü: Özel). Bu betik ağ profilini DEĞİŞTİRMEZ.
#
# Çalıştırma: PowerShell'i "Yönetici olarak çalıştır" ile açın, sonra:
#   powershell -ExecutionPolicy Bypass -File "D:\PROGRAMLARIM\QUALITY PROGRAM\tools\tablet_guvenlik_duvari.ps1"
# Geri almak: Remove-NetFirewallRule -DisplayName "Kalite YS tablet sunucusu (TCP 8765)"

$ErrorActionPreference = 'Stop'
$ad = 'Kalite YS tablet sunucusu (TCP 8765)'
$python = (Get-Command python).Source
if ($python -like '*WindowsApps*') { throw "Microsoft Store kısayolu bulundu; gerçek python.exe yolunu verin." }

Get-NetFirewallRule -DisplayName $ad -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $ad -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort 8765 -Program $python -Profile Private | Out-Null
"İzin eklendi: $python, TCP 8765, yalnız Özel ağ."

$profil = Get-NetConnectionProfile | Select-Object -First 1
if ($profil.NetworkCategory -ne 'Private') {
    "UYARI: '$($profil.Name)' ağı şu an '$($profil.NetworkCategory)'. Tabletin bağlanabilmesi için"
    "Ayarlar > Ağ ve İnternet > Wi-Fi > $($profil.Name) > Ağ profili türü: Özel yapın."
}
