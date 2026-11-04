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
        Write-Host "[错误] 未找到 ffmpeg.exe！" -ForegroundColor Red
        Write-Host "请确保 D:\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe 存在或配置了系统 PATH。"
        Read-Host "按回车键退出..."
        exit 1
    }
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   StimMusic 专属音频转码与优化工具 (16-bit PCM)" -ForegroundColor Cyan
Write-Host "   支持各类音频格式，完美适配 MDL3 原生 XAudio2 引擎" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "使用 ffmpeg: $ffmpeg`n"

$ar = 44100
$ac = 2

if (-not $Files -or $Files.Count -eq 0) {
    Write-Host "请选择音频转码预设 (100% 兼容游戏音频引擎)：" -ForegroundColor Yellow
    Write-Host "  [1] CD 高清立体声   (44.1kHz 16-bit 立体声，无损音质，推荐！)"
    Write-Host "  [2] 轻量紧凑立体声 (22.05kHz 16-bit 立体声，体积减半约 15MB)"
    Write-Host "  [3] 极致小体积单声道 (22.05kHz 16-bit 单声道，约 7.5MB，MP3大小)"
    Write-Host ""
    $choice = Read-Host "请输入选项 (直接回车默认选 1 [CD高清立体声])"

    if ($choice -eq "2") {
        $ar = 22050
        $ac = 2
        Write-Host "已选择: 轻量紧凑立体声 (22.05kHz 立体声)`n" -ForegroundColor Green
    } elseif ($choice -eq "3") {
        $ar = 22050
        $ac = 1
        Write-Host "已选择: 极致小体积单声道 (22.05kHz 单声道)`n" -ForegroundColor Green
    } else {
        $ar = 44100
        $ac = 2
        Write-Host "已选择: CD 高清立体声 (44.1kHz 立体声)`n" -ForegroundColor Green
    }

    # Step 1: scan compressed files (.m4s, .mp3, .mp4, .flac, .ogg)
    $sourceFiles = Get-ChildItem -File | Where-Object { $_.Extension -match '^\.(mp3|m4s|mp4|flac|ogg)$' }
    foreach ($f in $sourceFiles) {
        $outName = "$($f.BaseName).wav"
        Write-Host "正在转码转换: $($f.Name) -> $outName" -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $f.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $outName
        if ($LASTEXITCODE -eq 0) {
            $newSizeMB = [math]::Round((Get-Item $outName).Length / 1MB, 2)
            Write-Host "  [成功] $outName 已生成，体积: $newSizeMB MB" -ForegroundColor Green
        } else {
            Write-Host "  [失败] 转换 $($f.Name) 失败" -ForegroundColor Red
        }
    }

    # Step 2: scan existing WAV files and optimize
    $wavFiles = Get-ChildItem -File -Filter "*.wav" | Where-Object { $_.Name -notmatch '_pcm_tmp\.wav$' }
    foreach ($w in $wavFiles) {
        $oldSizeMB = [math]::Round($w.Length / 1MB, 2)
        $tmpName = "$($w.BaseName)_pcm_tmp.wav"
        Write-Host "正在优化转换: $($w.Name) (当前体积: $oldSizeMB MB)..." -ForegroundColor Yellow
        & $ffmpeg -y -v warning -i $w.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $tmpName
        if ($LASTEXITCODE -eq 0 -and (Test-Path $tmpName)) {
            $newSizeMB = [math]::Round((Get-Item $tmpName).Length / 1MB, 2)
            Move-Item -Path $tmpName -Destination $w.FullName -Force
            Write-Host "  [完成] $($w.Name) 已转为兼容 16-bit PCM: $oldSizeMB MB -> $newSizeMB MB！" -ForegroundColor Green
        }
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "所有音频处理完成！纯正 16-bit PCM，搭配分段流式加载，零卡顿流畅播放。" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Read-Host "按回车键退出..."
} else {
    Write-Host "[拖拽模式] 正在以 CD 高清立体声 (44.1kHz 16-bit PCM) 转换传入的文件..." -ForegroundColor Yellow
    foreach ($file in $Files) {
        if (Test-Path $file) {
            $item = Get-Item $file
            $outPath = Join-Path $item.DirectoryName "$($item.BaseName).wav"
            Write-Host "正在转换: $($item.Name) -> $($item.BaseName).wav" -ForegroundColor Yellow
            & $ffmpeg -y -v warning -i $item.FullName -map 0:a:0? -ac $ac -ar $ar -c:a pcm_s16le $outPath
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
