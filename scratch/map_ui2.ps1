$f = "c:\AI Project\Youtube_video\ui\index.html"
$pats = @('function (loadProjects|selectProject|setCurrentProject|onProjectChange|refreshProjects|selectCurrentProject)', 'id="project-select"', 'openStudioStage\(', "fetch\('/api/projects'\)")
Select-String -Path $f -Pattern $pats | ForEach-Object { $l=$_.Line.Trim(); "$($_.LineNumber): " + $l.Substring(0,[Math]::Min(150,$l.Length)) } | Select-Object -First 30
Select-String -Path "c:\AI Project\Youtube_video\core\project_manager.py" -Pattern 'def list_all' -Context 0,30 | ForEach-Object { $_.Context.PostContext }
