# StimMusic Audio Optimizer (16-bit PCM for MDL3 XAudio2)
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Files
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($scriptDir) { Set-Location $scriptDir }

$ffmpeg = "D:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) {
    $found = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($found) {
        $ffmpeg = "ffmpeg"
    } else {
        Write-Host "[ERROR / 错误] ffmpeg.exe not found / 未找到 ffmpeg.exe！" -ForegroundColor Red
        Write-Host "Please ensure ffmpeg is installed and in PATH, or at D:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe."
        Write-Host "请确保系统已安装 ffmpeg 并配置环境变量 PATH。"
        Read-Host "Press Enter to exit / 按回车键退出..."
        exit 1
    }
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   StimMusic Audio Converter & Optimizer (16-bit PCM for MDL3 XAudio2)" -ForegroundColor Cyan
Write-Host "   音频转码与优化工具 | 完美适配 MDL3 原生 XAudio2 音频引擎" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Using ffmpeg: $ffmpeg`n"

$ar = 44100
$ac = 2

if (-not $Files -or $Files.Count -eq 0) {
    Write-Host "Select Audio Preset / 请选择音频转码预设 (100% compatible):" -ForegroundColor Yellow
    Write-Host "  [1] CD Hi-Fi Stereo   (44.1kHz 16-bit Stereo, lossless / 无损音质，推荐！)"
    Write-Host "  [2] Compact Stereo    (22.05kHz 16-bit Stereo, half size ~15MB / 体积减半)"
    Write-Host "  [3] Ultra-light Mono  (22.05kHz 16-bit Mono, ~7.5MB / 极致小体积)"
    Write-Host ""
    $choice = Read-Host "Input option / 请输入选项 [1-3] (Default / 默认选 1)"

    if ($choice -eq "2") {
        $ar = 22050
        $ac = 2
        Write-Host "Selected: Compact Stereo (22.05kHz Stereo)`n" -ForegroundColor Green
    } elseif ($choice -eq "3") {
        $ar = 22050
        $ac = 1
        Write-Host "Selected: Ultra-light Mono (22.05kHz Mono)`n" -ForegroundColor Green
    } else {
        $ar = 44100
        $ac = 2
        Write-Host "Selected: CD Hi-Fi Stereo (44.1kHz Stereo)`n" -ForegroundColor Green
    }

    # Step 1: scan compressed files (.m4s, .mp3, .mp4, .flac, .ogg)
    $sourceFiles = Get-ChildItem -File | Where-Object { $_.Extension -eq ".mp3" -or $_.Extension -eq ".m4s" -or $_.Extension -eq ".mp4" -or $_.Extension -eq ".flac" -or $_.Extension -eq ".ogg" }
    foreach ($f in $sourceFiles) {
        $outName = "$($f.BaseName).wav"
        Write-Host "Converting / 正在转码转换: $($f.Name) -> $outName" -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $f.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $outName
        if ($LASTEXITCODE -eq 0) {
            $newSizeMB = [math]::Round((Get-Item $outName).Length / 1MB, 2)
            Write-Host "  [OK / 成功] $outName generated ($newSizeMB MB)" -ForegroundColor Green
        } else {
            Write-Host "  [FAILED / 失败] Failed to convert $($f.Name)" -ForegroundColor Red
        }
    }

    # Step 2: scan existing WAV files and optimize
    $wavFiles = Get-ChildItem -File -Filter "*.wav" | Where-Object { -not $_.Name.EndsWith("_pcm_tmp.wav") }
    foreach ($w in $wavFiles) {
        $oldSizeMB = [math]::Round($w.Length / 1MB, 2)
        $tmpName = "$($w.BaseName)_pcm_tmp.wav"
        Write-Host "Optimizing / 正在优化转换: $($w.Name) ($oldSizeMB MB)..." -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $w.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $tmpName
        if ($LASTEXITCODE -eq 0 -and (Test-Path $tmpName)) {
            $newSizeMB = [math]::Round((Get-Item $tmpName).Length / 1MB, 2)
            Move-Item -Path $tmpName -Destination $w.FullName -Force
            Write-Host "  [DONE / 完成] $($w.Name) -> 16-bit PCM: $oldSizeMB MB -> $newSizeMB MB" -ForegroundColor Green
        }
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "All audio files processed! Pure 16-bit PCM for stutter-free playback." -ForegroundColor Cyan
    Write-Host "所有音频转码完成！高保真 16-bit PCM，零卡顿流畅播放。" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Read-Host "Press Enter to exit / 按回车键退出..."
} else {
    Write-Host "[Drag & Drop Mode / 拖拽模式] Converting files to CD Hi-Fi Stereo (44.1kHz 16-bit PCM)..." -ForegroundColor Yellow
    foreach ($file in $Files) {
        if (Test-Path $file) {
            $item = Get-Item $file
            $outPath = Join-Path $item.DirectoryName "$($item.BaseName).wav"
            Write-Host "Converting / 正在转换: $($item.Name) -> $($item.BaseName).wav" -ForegroundColor Yellow
            & $ffmpeg -y -v warning -i $item.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $outPath
            if ($LASTEXITCODE -eq 0) {
                $szMB = [math]::Round((Get-Item $outPath).Length / 1MB, 2)
                Write-Host "  [OK / 成功] Generated $($item.BaseName).wav ($szMB MB)" -ForegroundColor Green
            } else {
                Write-Host "  [FAILED / 失败] Failed to convert $($item.Name)" -ForegroundColor Red
            }
        }
    }
    Read-Host "Press Enter to exit / 按回车键退出..."
}
