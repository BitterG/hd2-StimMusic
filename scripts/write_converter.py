from pathlib import Path

ps1_content = """# StimMusic Ultra-Lightweight Audio Converter (MS-ADPCM)
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Files
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($scriptDir) { Set-Location $scriptDir }

$ffmpeg = "D:\\ffmpeg-7.1.1-essentials_build\\bin\\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) {
    $found = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($found) {
        $ffmpeg = "ffmpeg"
    } else {
        Write-Host "[错误] 未找到 ffmpeg.exe！" -ForegroundColor Red
        Write-Host "请确保 D:\\ffmpeg-7.1.1-essentials_build\\bin\\ffmpeg.exe 存在或配置了系统 PATH。"
        Read-Host "按回车键退出..."
        exit 1
    }
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   StimMusic 音频超轻量转码工具 (MS-ADPCM)" -ForegroundColor Cyan
Write-Host "   彻底告别几十兆！轻松将音乐压缩至 MP3 大小 (3MB~5MB)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "使用 ffmpeg: $ffmpeg`n"

$ar = 32000
$ac = 2

if (-not $Files -or $Files.Count -eq 0) {
    Write-Host "请选择压缩体积预设：" -ForegroundColor Yellow
    Write-Host "  [1] MP3 标准体积 (32kHz 立体声，3分钟约 5.5MB，推荐！)"
    Write-Host "  [2] 极致小体积   (44.1kHz 单声道，3分钟约 3.8MB，与192k MP3相同)"
    Write-Host "  [3] 高保真立体声 (48kHz 立体声，3分钟约 8.5MB，战地5方案)"
    Write-Host ""
    $choice = Read-Host "请输入选项 (直接回车默认选 1 [MP3标准体积])"

    if ($choice -eq "2") {
        $ar = 44100
        $ac = 1
        Write-Host "已选择: 极致小体积 (单声道 44.1kHz)`n" -ForegroundColor Green
    } elseif ($choice -eq "3") {
        $ar = 48000
        $ac = 2
        Write-Host "已选择: 高保真立体声 (立体声 48kHz)`n" -ForegroundColor Green
    } else {
        $ar = 32000
        $ac = 2
        Write-Host "已选择: MP3 标准体积 (立体声 32kHz)`n" -ForegroundColor Green
    }

    # Step 1: scan compressed files (.m4s, .mp3, .mp4, .flac, .ogg)
    $sourceFiles = Get-ChildItem -File | Where-Object { $_.Extension -match '^\\.(mp3|m4s|mp4|flac|ogg)$' }
    foreach ($f in $sourceFiles) {
        $outName = "$($f.BaseName).wav"
        Write-Host "正在压缩转换: $($f.Name) -> $outName" -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $f.FullName -map 0:a:0? -ac $ac -ar $ar -c:a adpcm_ms -block_size 1024 $outName
        if ($LASTEXITCODE -eq 0) {
            $newSizeMB = [math]::Round((Get-Item $outName).Length / 1MB, 2)
            Write-Host "  [成功] $outName 已生成，体积: $newSizeMB MB" -ForegroundColor Green
        } else {
            Write-Host "  [失败] 转换 $($f.Name) 失败" -ForegroundColor Red
        }
    }

    # Step 2: scan existing WAV files and optimize
    $wavFiles = Get-ChildItem -File -Filter "*.wav" | Where-Object { $_.Name -notmatch '_adpcm_tmp\\.wav$' }
    foreach ($w in $wavFiles) {
        $oldSizeMB = [math]::Round($w.Length / 1MB, 2)
        $tmpName = "$($w.BaseName)_adpcm_tmp.wav"
        Write-Host "正在优化压缩: $($w.Name) (当前体积: $oldSizeMB MB)..." -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $w.FullName -map 0:a:0? -ac $ac -ar $ar -c:a adpcm_ms -block_size 1024 $tmpName
        if ($LASTEXITCODE -eq 0 -and (Test-Path $tmpName)) {
            $newSizeMB = [math]::Round((Get-Item $tmpName).Length / 1MB, 2)
            Move-Item -Path $tmpName -Destination $w.FullName -Force
            Write-Host "  [完成] $($w.Name) 已优化为轻量 MS-ADPCM: $oldSizeMB MB -> $newSizeMB MB！" -ForegroundColor Green
        }
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "所有音频处理完成！现在所有歌曲均已变成 MP3 大小，零卡顿流畅播放。" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Read-Host "按回车键退出..."
} else {
    Write-Host "[拖拽模式] 正在以 MP3 标准体积 (32kHz 立体声) 转换传入的文件..." -ForegroundColor Yellow
    foreach ($file in $Files) {
        if (Test-Path $file) {
            $item = Get-Item $file
            $outPath = Join-Path $item.DirectoryName "$($item.BaseName).wav"
            Write-Host "正在转换: $($item.Name) -> $($item.BaseName).wav" -ForegroundColor Yellow
            & $ffmpeg -y -v warning -i $item.FullName -map 0:a:0? -ac $ac -ar $ar -c:a adpcm_ms -block_size 1024 $outPath
            if ($LASTEXITCODE -eq 0) {
                $szMB = [math]::Round((Get-Item $outPath).Length / 1MB, 2)
                Write-Host "  [成功] 已生成 $($item.BaseName).wav ($szMB MB)" -ForegroundColor Green
            } else {
                Write-Host "  [失败] 转换 $($item.Name) 失败" -ForegroundColor Red
            }
        }
    }
    Read-Host "按回车键退出..."
}
"""

cmd_content = "@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%~dp0convert_track.ps1\" %*\r\n"

dirs = [
    Path(r'C:\Users\kugua\AppData\Local\CowboyBingus\Helldivers2\StimMusic'),
    Path(r'c:\Users\kugua\AppData\Local\hd2arsenal\mods\StimMusic-0.12.0_AR274594')
]

for d in dirs:
    (d / 'convert_track.ps1').write_text(ps1_content, encoding='utf-8-sig')
    (d / 'convert_track.cmd').write_text(cmd_content, encoding='ascii')
    print('Updated scripts in', d)
