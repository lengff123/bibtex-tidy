const i18n = {
    en: {
        // Options Panel
        options: "Options",
        header: "Enable header comments with processing information",
        
        // Formatting
        formatting: "Formatting",
        alignment: "Alignment",
        alignmentHint: "Alignment value for field values",
        doubleBraces: "Use double braces for values",
        useSpaces: "Use spaces instead of tabs for indentation",
        
        // Sorting & Duplicates
        sortingDuplicates: "Sorting & Duplicates",
        sortEntries: "Sort Entries",
        sortNone: "None (preserve order)",
        sortKey: "By citation key",
        sortYear: "By year",
        sortAuthor: "By author",
        duplicateCheck: "Duplicate Check",
        duplicateNone: "None",
        duplicateKey: "By key",
        duplicateDoi: "By DOI",
        duplicateTitle: "By title",
        duplicateAll: "All methods",
        mergeStrategy: "Merge Strategy",
        mergeCombine: "Combine",
        mergeOverwrite: "Overwrite",
        mergeFirst: "Keep first",
        mergeLast: "Keep last",

        // Field Processing
        fieldProcessing: "Field Processing",
        fieldOrder: "Field Order",
        fieldOrderHint: "Comma-separated list of fields in desired order",
        omitFields: "Omit Fields",
        omitFieldsHint: "Fields to omit (comma-separated)",
        replaceFields: "Replace Fields",
        replaceFieldsHint: "Format: old1:new1,old2:new2",
        sortFields: "Enable field sorting",

        // Author Processing
        authorProcessing: "Author Processing",
        maxAuthors: "Max Authors",
        maxAuthorsHint: "Maximum number of authors before truncating",

        // URL Processing
        urlProcessing: "URL Processing",
        encodeUrls: "Enable URL encoding",
        validateUrls: "Check if URLs are accessible",

        // Citation Keys
        citationKeys: "Citation Keys",
        autoKeys: "Automatically generate citation keys",
        keyFormat: "Key Format",
        keyFormatHint: "Format for citation keys (e.g., \"[auth][year][title:3]\")",

        // UI Elements
        process: "Process",
        donate: "Donate to Support BibTeX Tidy ☕",
        editor: "BibTeX Editor"
    },
    zh: {
        // 选项面板
        options: "选项",
        header: "启用包含处理信息的头部注释",
        
        // 格式化
        formatting: "格式化",
        alignment: "对齐",
        alignmentHint: "字段值的对齐值",
        doubleBraces: "使用双括号包围值",
        useSpaces: "使用空格代替制表符进行缩进",
        
        // 排序和重复项
        sortingDuplicates: "排序与重复项",
        sortEntries: "条目排序",
        sortNone: "无（保持原顺序）",
        sortKey: "按引用键",
        sortYear: "按年份",
        sortAuthor: "按作者",
        duplicateCheck: "重复检查",
        duplicateNone: "无",
        duplicateKey: "按键",
        duplicateDoi: "按 DOI",
        duplicateTitle: "按标题",
        duplicateAll: "所有方法",
        mergeStrategy: "合并策略",
        mergeCombine: "合并",
        mergeOverwrite: "覆盖",
        mergeFirst: "保留首个",
        mergeLast: "保留最后",

        // 字段处理
        fieldProcessing: "字段处理",
        fieldOrder: "字段顺序",
        fieldOrderHint: "按期望顺序排列的字段（逗号分隔）",
        omitFields: "忽略字段",
        omitFieldsHint: "要忽略的字段（逗号分隔）",
        replaceFields: "替换字段",
        replaceFieldsHint: "格式：旧1:新1,旧2:新2",
        sortFields: "启用字段排序",

        // 作者处理
        authorProcessing: "作者处理",
        maxAuthors: "最大作者数",
        maxAuthorsHint: "截断前的最大作者数量",

        // URL处理
        urlProcessing: "URL处理",
        encodeUrls: "启用URL编码",
        validateUrls: "检查URL可访问性",

        // 引用键
        citationKeys: "引用键",
        autoKeys: "自动生成引用键",
        keyFormat: "键格式",
        keyFormatHint: "引用键格式（例如：\"[auth][year][title:3]\"）",

        // 界面元素
        process: "处理",
        donate: "赞助支持 BibTeX Tidy ☕",
        editor: "BibTeX 编辑器"
    }
};

// 添加语言检测和自动设置功能
function detectLanguage() {
    // 获取浏览器语言设置
    const browserLang = navigator.language || navigator.userLanguage;
    
    // 首选项：先检查 localStorage 中保存的语言设置
    const savedLang = localStorage.getItem('preferred-language');
    if (savedLang && ['en', 'zh'].includes(savedLang)) {
        return savedLang;
    }
    
    // 如果没有保存的设置，根据浏览器语言判断
    if (browserLang.startsWith('zh')) {
        return 'zh';
    }
    
    // 默认使用英文
    return 'en';
}

// 导出检测函数和翻译对象
export { i18n as default, detectLanguage };