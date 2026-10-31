$pat = 'switchTab\(|id="tab-|function (openStudio|renderStudio|loadStudio|switchTab|isDramaStudioProject|selectCreatorMode|setCreatorMode|switchStudio)|STAGE_META(_DRAMA)? = |studio-mode|nav-tab'
Select-String -Path "c:\AI Project\Youtube_video\ui\index.html" -Pattern $pat | ForEach-Object {
  $l = $_.Line.Trim(); "$($_.LineNumber): " + $l.Substring(0, [Math]::Min(150, $l.Length))
} | Select-Object -First 60
