# Génère une clé secrète aléatoire (32 octets, hexadécimal) pour .env.local
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
'SECRET_KEY=' + (($b | ForEach-Object { $_.ToString('x2') }) -join '')
