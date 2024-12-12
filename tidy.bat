@echo off
setlocal enabledelayedexpansion

:: 检查 PPT 目录是否存在
if not exist "PPT\" (
    echo Error: PPT directory not found!
    pause
    exit /b 1
)

:: 合并 PPT 目录下所有的 .bib 文件到当前目录的 ref_temp.bib
echo Merging all .bib files from PPT directory to ref_temp.bib...
copy /b nul ref_temp.bib >nul
for /r "PPT" %%f in (*.bib) do (
    echo Merging: %%f
    type "%%f" >> ref_temp.bib
    echo. >> ref_temp.bib
)

:: 执行 bibtex-tidy 命令处理合并后的文件
echo.
echo Tidying ref_temp.bib...
bib-tidy ^
    --omit=abstract,langid,annotation,url,urldate,file,eventtitle,keywords ^
    --curly ^
    --numeric ^
    --tab ^
    --align=13 ^
    --duplicates=key ^
    --merge=combine ^
    --sort-fields ^
    --encode-urls ^
    --no-tidy-comments ^
    --remove-empty-fields ^
    --max-authors=3 ^
    --output="ref_temp.bib" ^
    "ref_temp.bib"

if errorlevel 1 (
    echo Error: bibtex-tidy failed to process the file.
) else (
    echo Successfully processed ref_temp.bib
)

pause