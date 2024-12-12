import os
import re
import urllib.parse
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Set, Tuple
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from difflib import SequenceMatcher
from datetime import datetime
from pybtex.database import Entry
import unicodedata
import string

class BibTidy:
    def __init__(self, options):
        """初始化BibTidy类
        
        Args:
            options: 配置选项字典，包含各种处理参数
        """
        # 保存配置选项
        self.options = options
        self.protect_caps_fields = [
        # 标题相关
        'title', 'booktitle', 'chapter', 'subtitle', 'maintitle',
        'shorttitle', 'titleaddon', 'booktitleaddon',
        
        # 期刊相关
        'journal', 'journaltitle', 'journalsubtitle', 'issuetitle',
        
        # 出版相关
        'publisher', 'organization', 'institution', 'school',
        'institute', 'venue', 'series', 'collection',
        
        # 会议相关
        'conference', 'meeting', 'event', 'venue',
        'eventtitle', 'eventname',
        
        # 地点相关
        'location', 'address', 'venue', 'city', 'country',
        
        # 机构相关
        'institution', 'department', 'faculty', 'institute',
        'school', 'university', 'organization', 'publisher',
        
        # 其他
        'type', 'howpublished', 'note', 'addendum',
        'annotation', 'library', 'series', 'collection'
        ]
        # 检查用户是否提供了自定义字段顺序
        if 'field_order' in options and options['field_order']:
            self.field_order = [field.strip() for field in options['field_order'].split(',')]
        else:
            # 默认字段顺序
            self.field_order = [
                'title', 'shorttitle', 'author', 'year', 'month', 'day',
                'journal', 'booktitle', 'location', 'publisher', 'address',
                'series', 'volume', 'number', 'pages', 'doi', 'isbn',
                'issn', 'url', 'urldate', 'copyright', 'category', 'note'
            ]
        
        # 月份名称到标准缩写的映射
        self.month_abbrev = {
            'january': 'jan', 'february': 'feb', 'march': 'mar',
            'april': 'apr', 'may': 'may', 'june': 'jun',
            'july': 'jul', 'august': 'aug', 'september': 'sep',
            'october': 'oct', 'november': 'nov', 'december': 'dec'
        }
        
        # 从选项中获取字段替换映射，用于重命名字段
        self.field_replacements = options.get('field_replacements', {})
        
        # 定义作者名之间的标准分隔符
        self.author_separator = ' and '
        
        # 从选项中获取引用键的格式模板，默认使用作者+年份
        self.key_format = options.get('key_format', '[auth][year][title:3]')
        
        # 定义不同类型条目期刊所需的必填字段
        self.required_fields = {
            'article': ['author', 'title', 'journal', 'year', 'volume', 'number', 'pages', 'doi', 'issn'],
            'book': ['author', 'title', 'publisher', 'year', 'isbn', 'doi'],
            'inproceedings': ['author', 'title', 'booktitle', 'year', 'pages', 'doi'],
            'incollection': ['author', 'title', 'booktitle', 'publisher', 'year', 'pages', 'doi'],
            'phdthesis': ['author', 'title', 'school', 'year', 'doi'],
            'mastersthesis': ['author', 'title', 'school', 'year', 'doi'],
            'techreport': ['author', 'title', 'institution', 'year', 'number', 'doi'],
            'default': ['author', 'title', 'year', 'doi']
        }
        

    def find_duplicates(self, entries: List[Dict]) -> Dict[str, List[Dict]]:
        """使用优化的方法查找重复条目"""
        duplicates = {}
        
        # 创建索引以加速查找
        doi_index = {}
        title_cache = {}  # 缓存标准化后的标题
        author_year_index = {}
        
        # 预处理和索引创建
        for entry in entries:
            key = entry['ID']
            
            # DOI 索引
            if 'doi' in entry:
                doi = entry['doi'].lower()
                if doi not in doi_index:
                    doi_index[doi] = []
                doi_index[doi].append(entry)
            
            # 标题索引（使用缓存）
            if 'title' in entry:
                norm_title = self.normalize_text(entry['title'])
                title_cache[id(entry)] = norm_title
            
            # 作者年份索引
            if 'author' in entry and 'year' in entry:
                author_year = (self.normalize_text(entry['author']), entry['year'])
                if author_year not in author_year_index:
                    author_year_index[author_year] = []
                author_year_index[author_year].append(entry)
        
        # 查找重复
        for i, entry1 in enumerate(entries):
            key = entry1['ID']
            if key not in duplicates:
                duplicates[key] = []
            duplicates[key].append(entry1)
            
            check_method = self.options.get('duplicate_check', 'all')
            
            # 根据不同的查重策略检查重复
            if check_method == 'doi':
                # 仅检查DOI
                if 'doi' in entry1:
                    doi = entry1['doi'].lower()
                    matches = doi_index.get(doi, [])
                    duplicates[key].extend([e for e in matches if e != entry1])
            
            elif check_method == 'title':
                # 仅检查标题相似度
                if 'title' in entry1:
                    norm_title1 = title_cache[id(entry1)]
                    for entry2 in entries[i+1:]:
                        if 'title' in entry2:
                            norm_title2 = title_cache[id(entry2)]
                            if SequenceMatcher(None, norm_title1, norm_title2).ratio() > 0.85:
                                duplicates[key].append(entry2)
            
            elif check_method == 'author_year':
                # 仅检查作者和年份组合
                if 'author' in entry1 and 'year' in entry1:
                    author_year = (self.normalize_text(entry1['author']), entry1['year'])
                    matches = author_year_index.get(author_year, [])
                    duplicates[key].extend([e for e in matches if e != entry1])
            
            else:  # 'all' - 使用所有检查方法
                is_duplicate_set = set()  # 用集合避免重复添加
                
                # 检查DOI
                if 'doi' in entry1:
                    doi = entry1['doi'].lower()
                    matches = doi_index.get(doi, [])
                    is_duplicate_set.update(id(e) for e in matches if e != entry1)
                
                # 检查标题相似度
                if 'title' in entry1:
                    norm_title1 = title_cache[id(entry1)]
                    for entry2 in entries[i+1:]:
                        if id(entry2) not in is_duplicate_set and 'title' in entry2:
                            norm_title2 = title_cache[id(entry2)]
                            if SequenceMatcher(None, norm_title1, norm_title2).ratio() > 0.85:
                                is_duplicate_set.add(id(entry2))
                
                # 检查作者和年份组合
                if 'author' in entry1 and 'year' in entry1:
                    author_year = (self.normalize_text(entry1['author']), entry1['year'])
                    matches = author_year_index.get(author_year, [])
                    is_duplicate_set.update(id(e) for e in matches if e != entry1)
                
                # 将找到的重复项添加到结果中
                duplicates[key].extend([e for e in entries if id(e) in is_duplicate_set])
        
        # 只返回实际有重复的条目
        return {k: v for k, v in duplicates.items() if len(v) > 1}

    def merge_entries(self, entries: List[Dict]) -> List[Dict]:
        """根据不同策略合并重复条目"""
        duplicates = self.find_duplicates(entries)
        merged = []
        
        for entry in entries:
            if entry['ID'] in duplicates:
                dups = duplicates[entry['ID']]
                if self.options['merge_strategy'] == 'first':
                    merged.append(dups[0])
                elif self.options['merge_strategy'] == 'last':
                    merged.append(dups[-1])
                elif self.options['merge_strategy'] == 'overwrite':
                    # 使用最新的条目覆盖
                    merged.append(dups[-1])
                else:  # 'combine'
                    # 合并所有字段
                    merged_entry = {}
                    all_dups = dups
                    
                    # 选择最完整的条目作为基础
                    base_entry = max(all_dups, key=lambda x: len(x))
                    merged_entry.update(base_entry)
                    
                    # 合并其他条目的额外信息
                    for dup in all_dups:
                        for field, value in dup.items():
                            if field not in merged_entry:
                                merged_entry[field] = value
                            elif field in ['abstract', 'note']:
                                # 对于某些字段，保留最长的版本
                                if len(value) > len(merged_entry[field]):
                                    merged_entry[field] = value
                            elif field == 'author':
                                # 使用最标准的作者格式
                                merged_entry[field] = self.standardize_author_name(value)
                    
                    merged.append(merged_entry)
            elif entry['ID'] not in duplicates:
                merged.append(entry)

        return merged
    

    def resolve_key_conflicts(self, entries: List[Dict]) -> List[Dict]:
        """解决引用键冲突"""
        key_count = {}
        resolved_entries = []
        
        for entry in entries:
            key = entry['ID']
            if key in key_count:
                key_count[key] += 1
                entry['ID'] = f"{key}_{chr(96 + key_count[key])}"  # 添加 a, b, c 等后缀
            else:
                key_count[key] = 1
            resolved_entries.append(entry)
        
        return resolved_entries

    
    def normalize_text(self, text: str) -> str:
        """标准化文本以进行比较"""
        # 转换为小写
        text = text.lower()
        # 删除标点符号
        text = text.translate(str.maketrans('', '', string.punctuation))
        # 标准化Unicode字符
        text = unicodedata.normalize('NFKD', text)
        # 删除额外的空格
        text = ' '.join(text.split())
        return text


    def standardize_author_name(self, author: str) -> str:
        """标准化作者姓名格式"""
        if not author:
            return author
        
        # 移除多余的大括号
        author = author.strip('{}')
        
        # 处理新格式 (Family=X and Given=Y)
        if 'Family=' in author:
            names = []
            current_author = {}  # 存储当前作者的各个组成部分
            
            # 按 and 分割多个作者
            for part in author.split(' and '):
                # 解析每个作者的组成部分(Family/Given/Prefix等)
                for component in part.split(' '):
                    if '=' in component:
                        key, value = component.split('=')
                        current_author[key.lower()] = value
                        
                # 组装当前作者的完整名字
                if current_author:
                    name_parts = []
                    # 如果有前缀且需要使用前缀
                    if current_author.get('prefix') and current_author.get('useprefix', '').lower() == 'true':
                        name_parts.append(current_author['prefix'])
                    # 添加姓氏
                    if current_author.get('family'):
                        name_parts.append(current_author['family'])
                    # 添加名字
                    if current_author.get('given'):
                        name_parts.append(current_author['given'])
                        
                    # 将所有部分用逗号连接
                    names.append(', '.join(filter(None, name_parts)))
                    current_author = {}  # 重置当前作者信息
            
            return ' and '.join(names)
        
        # 处理标准格式 (Lastname, Firstname and Lastname, Firstname)
        elif ' and ' in author:
            # 直接返回标准格式
            return author
        
        # 处理错误格式 (Chen and Chiu-hung)
        else:
            parts = author.split(' and ')
            formatted_names = []
            
            # 每两个部分组成一个完整的姓名
            for i in range(0, len(parts), 2):
                if i + 1 < len(parts):
                    surname = parts[i].strip()
                    given_name = parts[i + 1].strip()
                    formatted_names.append(f"{surname}, {given_name}")
            
            return ' and '.join(formatted_names)
    
    def standardize_pages(self, pages: str) -> str:
        """标准化页码格式"""
        if not pages:
            return pages
        # 将各种分隔符统一为破折号
        pages = re.sub(r'[-–—]+', '--', pages)
        # 删除空格
        pages = pages.replace(' ', '')
        return pages

    def standardize_entry(self, entry: Dict) -> Dict:
        """标准化条目的各个字段"""
        for field, value in entry.items():
            if not isinstance(value, str):
                continue
            """标准化条目的各个字段"""
            for field, value in entry.items():
                if field == 'author':
                    entry[field] = self.standardize_author_name(value)
                    # 处理作者数量限制
                    if 'max_authors' in self.options:
                        authors = entry[field].split(self.author_separator)
                        if len(authors) > self.options['max_authors']:
                            entry[field] = self.author_separator.join(
                                authors[:self.options['max_authors']]) + ' and others'
                elif field == 'pages':
                    entry[field] = self.standardize_pages(value)
                elif field == 'month':
                    # 标准化月份缩写
                    value_lower = value.lower()
                    if value_lower in self.month_abbrev:
                        entry[field] = self.month_abbrev[value_lower]
                elif field == 'year':
                    # 确保年份格式正确
                    entry[field] = re.sub(r'[^0-9]', '', value)
                elif field == 'doi':
                    # 标准化DOI格式
                    entry[field] = value.lower().strip()
                elif field == 'url':
                    if self.options.get('encode_urls'):
                        entry[field] = urllib.parse.quote(value)
                    if not re.match(r'^https?://', entry[field]):
                        entry[field] = 'https://' + entry[field]
                elif field == 'date':
                    # 处理日期字段
                    # 尝试从日期中提取年份和月份
                    match = re.match(r'(\d{4})-(\d{1,2})', value)
                    if match:
                        year, month = match.groups()
                        entry['year'] = year
                        # 将月份数字转换为缩写
                        month_num = int(month)
                        if 1 <= month_num <= 12:
                            month_names = list(self.month_abbrev.values())
                            entry['month'] = month_names[month_num - 1]
                        # 可以选择删除原始date字段
                        del entry[field]
            
        return entry

    def generate_citation_key(self, entry: Dict) -> str:
        """使用 pybtex 生成引用键
        
        支持的格式选项：
        [auth] - 第一作者姓氏
        [auth:N] - 前N个作者姓氏
        [authors] - 所有作者姓氏
        [year] - 出版年份
        [title:N] - 标题前N个字符
        [journal:N] - 期刊名前N个字符
        [keyword:N] - 第一个关键词前N个字符
        """
        try:
            # 创建 pybtex Entry 对象
            pybtex_entry = Entry(entry['ENTRYTYPE'], fields=entry)
            key = self.key_format
            
            # 处理作者相关的占位符
            if '[auth' in key or '[authors]' in key:
                authors = pybtex_entry.persons.get('author', [])
                author_last_names = [author.last_names[0] for author in authors if author.last_names]
                
                # 处理 [auth:N]
                auth_n_match = re.search(r'\[auth:(\d+)\]', key)
                if auth_n_match:
                    n = int(auth_n_match.group(1))
                    auth_str = ''.join(author_last_names[:n])
                    key = re.sub(r'\[auth:\d+\]', auth_str, key)
                
                # 处理 [auth]
                if '[auth]' in key and author_last_names:
                    key = key.replace('[auth]', author_last_names[0])
                
                # 处理 [authors]
                if '[authors]' in key:
                    key = key.replace('[authors]', ''.join(author_last_names))
            
            # 处理年份
            if '[year]' in key:
                year = entry.get('year', '')
                key = key.replace('[year]', year)
            
            # 处理标题
            if '[title' in key:
                title = entry.get('title', '')
                # 处理 [title:N]
                title_n_match = re.search(r'\[title:(\d+)\]', key)
                if title_n_match:
                    n = int(title_n_match.group(1))
                    title_str = re.sub(r'[^\w]', '', title)[:n]
                    key = re.sub(r'\[title:\d+\]', title_str, key)
            
            # 处理期刊
            if '[journal' in key:
                journal = entry.get('journal', '')
                # 处理 [journal:N]
                journal_n_match = re.search(r'\[journal:(\d+)\]', key)
                if journal_n_match:
                    n = int(journal_n_match.group(1))
                    journal_str = re.sub(r'[^\w]', '', journal)[:n]
                    key = re.sub(r'\[journal:\d+\]', journal_str, key)
            
            # 处理关键词
            if '[keyword' in key:
                keywords = entry.get('keywords', '').split(',')
                if keywords:
                    # 处理 [keyword:N]
                    keyword_n_match = re.search(r'\[keyword:(\d+)\]', key)
                    if keyword_n_match:
                        n = int(keyword_n_match.group(1))
                        keyword_str = re.sub(r'[^\w]', '', keywords[0])[:n]
                        key = re.sub(r'\[keyword:\d+\]', keyword_str, key)
            
            # 移除特殊字符并确保键的唯一性
            key = re.sub(r'[^a-zA-Z0-9]', '', key)
            return key
            
        except Exception as e:
            print(f"Warning: Error generating citation key: {e}")
            return f"cite_{hash(str(entry))}"

    def validate_entry(self, entry: Dict) -> List[str]:
        """验证条目的有效性，返回错误信息列表"""
        errors = []
        
        # 检查必填字段
        entry_type = entry.get('ENTRYTYPE', 'default')
        required = self.required_fields.get(entry_type, self.required_fields['default'])
        
        for field in required:
            if field not in entry or not entry[field].strip():
                errors.append(f"Missing required field: {field}")
        
        # 验证 DOI
        if 'doi' in entry:
            doi = entry['doi']
            if not re.match(r'^10\.\d{4,9}/[-._;()/:\w]+$', doi):
                errors.append(f"Invalid DOI format: {doi}")
        
        # 验证 URL
        if 'url' in entry and self.options.get('validate_urls', False):
            url = entry['url']
            try:
                import requests
                response = requests.head(url, timeout=5)
                if response.status_code >= 400:
                    errors.append(f"URL not accessible: {url}")
            except Exception as e:
                errors.append(f"Error checking URL {url}: {str(e)}")
        
        # 验证日期
        if 'year' in entry:
            year = entry['year']
            if not re.match(r'^\d{4}$', year):
                errors.append(f"Invalid year format: {year}")
            
            current_year = datetime.now().year
            if int(year) > current_year:
                errors.append(f"Year {year} is in the future")
        
        if 'month' in entry:
            month = entry['month'].lower()
            if month not in self.month_abbrev and month not in self.month_abbrev.values():
                errors.append(f"Invalid month: {month}")
        
        return errors
    
    def sort_fields(self, entry: Dict) -> Dict:
        """按指定顺序排序字段"""
        sorted_entry = {}
        # 首先保留ID字段
        if 'ID' in entry:
            sorted_entry['ID'] = entry['ID']
        
        # 按照预定义顺序添加字段
        for field in self.field_order:
            if field in entry:
                sorted_entry[field] = entry[field]
        
        # 添加未在排序列表中的字段
        for key in entry:
            if key not in sorted_entry:
                sorted_entry[key] = entry[key]
        
        return sorted_entry
    
    def process_entry(self, entry: Dict) -> Dict:
        """处理单个条目的所有规则
        
        处理顺序：
        1. 验证检查 - 及早发现问题
        2. 字段替换 - 在其他处理前标准化字段名
        3. 删除字段 - 及早移除不需要的内容
        4. 内容标准化 - 处理作者、月份等
        5. 格式化处理 - 处理特殊字符、大括号等
        6. 引用键生成 - 基于处理后的内容生成
        """
        # 1. 验证检查
        if any(key in self.options for key in ['validate_urls', 'max_authors']):
            errors = self.validate_entry(entry)
            if errors:
                print(f"Warnings for entry {entry.get('ID', 'Unknown')}:")
                for error in errors:
                    print(f"  - {error}")
        
        # 2. 字段替换
        if 'field_replacements' in self.options:
            for old_field, new_field in self.options['field_replacements'].items():
                if old_field in entry:
                    entry[new_field] = entry.pop(old_field)
        
        # 3. 删除字段
        if 'omit_fields' in self.options:
            for field in self.options['omit_fields']:
                entry.pop(field, None)
        # 3.1 删除空字段
        entry = {k: v for k, v in entry.items() if v.strip()}
        
        # 4. 内容标准化
        entry = self.standardize_entry(entry)
        
        # 5. 特殊字符格式化处理
        for key, value in entry.items():
            if isinstance(value, str):
                # 将多个反斜杠规范化为两个
                value = re.sub(r'\\+', '\\\\', value)
                
                # 处理其他特殊字符
                value = value.replace('&', '\\&')\
                            .replace('%', '\\%')\
                            .replace('$', '\\$')\
                            .replace('#', '\\#')\
                            .replace('_', '\\_')\
                            .replace('{', '\\{')\
                            .replace('}', '\\}')\
                            .replace('~', '\\textasciitilde{}')\
                            .replace('^', '\\textasciicircum{}')
                entry[key] = value

        # 6. 大写字母保护处理
        use_braces = self.options.get('double_braces') or self.options.get('use_curly')
        if use_braces:
            for field in self.protect_caps_fields:
                if field in entry:
                    value = entry[field]
                    # 找出需要保护的大写单词
                    protected_words = re.findall(
                        r'(?:^|\:\s+)([A-Z][a-z]+)|([A-Z][A-Z]+)|([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*)',
                        value
                    )
                    # 为每个大写单词添加大括号保护
                    for match in protected_words:
                        word = next(w for w in match if w)
                        if not word.startswith('{') and not word.endswith('}'):
                            if self.options.get('double_braces'):
                                value = value.replace(word, '{{' + word + '}}')
                            else:  # use_curly
                                value = value.replace(word, '{' + word + '}')
                    entry[field] = value

        # 6. 生成引用键（放在最后，因为可能依赖于处理后的字段值）
        if self.options.get('auto_generate_keys'):
            entry['ID'] = self.generate_citation_key(entry)
        
        return entry
    

    
    def _process_chunk(self, entries: List[Dict]) -> List[Dict]:
        """处理一组条目"""
        return [self.process_entry(entry) for entry in entries]
    def process_entries_parallel(self, entries: List[Dict]) -> List[Dict]:
        """并行处理多个条目
        
        Args:
            entries: 要处理的条目列表
            
        Returns:
            处理后的条目列表
        """
        # 获取CPU核心数，留一个核心给系统
        max_workers = max(1, multiprocessing.cpu_count() - 1)
        # 使用更高效的分块策略
        chunk_size = max(1, len(entries) // (multiprocessing.cpu_count() - 1))
        chunks = [entries[i:i + chunk_size] for i in range(0, len(entries), chunk_size)]
        
        processed_entries = []
        
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # 批量处理条目
                future_to_chunk = {
                    executor.submit(self._process_chunk, chunk): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # 按顺序收集结果
                for future in as_completed(future_to_chunk):
                    chunk_entries = future.result()
                    processed_entries.extend(chunk_entries)
            
            return processed_entries
            
        except Exception as e:
            print(f"Error in parallel processing: {str(e)}")
            return [self.process_entry(entry) for entry in entries]
        

    def process_file(self, input_file: str, output_file: str = None):
        """处理整个bib文件
        
        处理顺序：
        1. 文件读取和基本清理
        2. 单条目处理（格式化、标准化等）
        3. 字段排序（如果启用）
        4. 重复条目处理
        5. 引用键处理
        6. 条目排序
        7. 配置输出格式
            - 缩进设置
            - 条目间空行
            - 字段值对齐
            - 字段显示顺序
        8. 文件写入
        """
        if output_file is None:
            output_file = input_file
            
        # 1. 文件读取和基本清理
        with open(input_file, 'r', encoding='utf-8') as bibtex_file:
            bib_database = bibtexparser.load(bibtex_file)
        
        # 移除条目类型中的额外大括号
        for entry in bib_database.entries:
            if 'ENTRYTYPE' in entry:
                entry['ENTRYTYPE'] = entry['ENTRYTYPE'].strip('{}')
        
        # 2. 并行处理条目
        processed_entries = self.process_entries_parallel(bib_database.entries)
        
        # 3. 字段排序（如果启用）
        if self.options.get('sort_fields'):
            processed_entries = [self.sort_fields(entry) for entry in processed_entries]
        
        # 4. 重复条目处理
        if self.options.get('merge_duplicates'):
            processed_entries = self.merge_entries(processed_entries)
        
        # 5. 引用键处理
        if self.options.get('auto_generate_keys'):
            processed_entries = self.resolve_key_conflicts(processed_entries)
        
        # 6. 条目排序
        if self.options.get('sort_entries'):
            sort_by = self.options['sort_entries']
            if sort_by == 'key':
                processed_entries.sort(key=lambda x: x['ID'].lower())
            elif sort_by == 'year':
                processed_entries.sort(key=lambda x: x.get('year', ''))
            elif sort_by == 'author':
                processed_entries.sort(key=lambda x: x.get('author', '').lower())
        
        # 7. 配置输出格式
        writer = BibTexWriter()
        # 7.1 缩进设置
        writer.indent = '\t' if self.options.get('use_tabs', True) else '  '
        
        # 7.2 条目间空行控制
        writer.add_trailing_comma = True
        writer.entry_separator = '\n' * (self.options.get('entry_spacing', 1) + 1)
        
        # 7.3 字段值对齐
        if 'align_values' in self.options:
            writer.align_values = self.options['align_values']
        
        # 7.4 字段显示顺序
        if hasattr(self, 'field_order'):
            writer.display_order = self.field_order
        
        # 7.5 禁用默认排序
        writer.order_entries_by = None    
   
        # 保存文件
        db = BibDatabase()
        db.entries = processed_entries
        
        # 添加文件头注释，只包含实际使用的选项
        if self.options.get('header'):
            header_options = []
            if 'max_authors' in self.options:
                header_options.append(f"Max authors: {self.options['max_authors']}")
            if 'align_values' in self.options:
                header_options.append(f"Alignment: {self.options['align_values']}")
            if 'double_braces' in self.options:
                header_options.append(f"Double braces: {self.options['double_braces']}")
            if 'sort_fields' in self.options:
                header_options.append(f"Sort fields: {self.options['sort_fields']}")
            if 'sort_entries' in self.options:
                header_options.append(f"Sort entries by: {self.options['sort_entries']}")
            if 'encode_urls' in self.options:
                header_options.append(f"Encode URLs: {self.options['encode_urls']}")
            if 'omit_fields' in self.options:
                header_options.append(f"Omitted fields: {', '.join(self.options['omit_fields'])}")
            if 'duplicate_check' in self.options:
                header_options.append(f"Duplicate check: {self.options['duplicate_check']}")
            if 'use_tabs' in self.options:
                header_options.append(f"Use spaces: {not self.options['use_tabs']}")
            if 'field_replacements' in self.options and self.options['field_replacements']:
                replacements = ', '.join(f"{k}:{v}" for k, v in self.options['field_replacements'].items())
                header_options.append(f"Field replacements: {replacements}")
            if 'merge_strategy' in self.options:
                header_options.append(f"Merge strategy: {self.options['merge_strategy']}")
            if 'key_format' in self.options:
                header_options.append(f"Key format: {self.options['key_format']}")
            if 'auto_generate_keys' in self.options:
                header_options.append(f"Auto-generate keys: {self.options['auto_generate_keys']}")
            if 'validate_urls' in self.options:
                header_options.append(f"Validate URLs: {self.options['validate_urls']}")
            if 'entry_spacing' in self.options:
                header_options.append(f"Entry spacing: {self.options['entry_spacing']}")
            
            
            # 获取原始条目数量
            original_count = len(bib_database.entries)
            # 获取处理后条目数量
            processed_count = len(processed_entries)
            # 计算重复条目数量
            duplicate_count = original_count - processed_count if self.options.get('merge_duplicates') else 0

            header = (
                f"% Bibliography File\n"
                f"% Processed by BibTidy on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"% Original entries: {original_count}\n"
                f"% Processed entries: {processed_count}\n"
                f"% Duplicate entries: {duplicate_count}\n"
            )
            
            if header_options:
                header += "% Options used:\n"
                for option in header_options:
                    header += f"%   - {option}\n"
            
            header += f"% {'='*76}\n\n"
            
            with open(output_file, 'w', encoding='utf-8') as bibtex_file:
                bibtex_file.write(header)
                bibtex_file.write(writer.write(db))

        else:
            # 不生成文件头注释，直接写入处理后的内容
            with open(output_file, 'w', encoding='utf-8') as bibtex_file:
                bibtex_file.write(writer.write(db))



def process_directory(directory: str, options: Dict):
    """处理目录下的所有bib文件"""
    processor = BibTidy(options)
    for file in os.listdir(directory):
        if file.endswith('.bib'):
            input_path = os.path.join(directory, file)
            output_path = os.path.join(directory, f"processed_{file}")
            print(f"Processing {file}...")
            processor.process_file(input_path, output_path)
            print(f"Saved to {output_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced BibTeX file processor')
    # Required arguments
    parser.add_argument('input', help='Input .bib file or directory')
    parser.add_argument('--output', help='Output file (optional)')

    
    # Optional features - all disabled by default

    # 格式化选��
    parser.add_argument('--align', type=int,
                      help='Alignment value for field values')
    parser.add_argument('--double-braces', action='store_true',
                      help='Use double braces for values')
    parser.add_argument('--use-spaces', action='store_true',
                      help='Use spaces instead of tabs for indentation')

    # 字段处理选项
    parser.add_argument('--field-order', help='Comma-separated list of fields in the desired order')
    parser.add_argument('--entry-spacing', type=int, default=1,
                      help='Number of blank lines between entries (default: 1)')
    parser.add_argument('--omit', help='Fields to omit (comma-separated)')
    parser.add_argument('--replace-fields',
                      help='Replace field names (format: old1:new1,old2:new2)')
    parser.add_argument('--sort-fields', action='store_true',
                      help='Enable field sorting')

    # 作者处理选项
    parser.add_argument('--max-authors', type=int,
                      help='Maximum number of authors before truncating')

    # URL处理选项
    parser.add_argument('--encode-urls', action='store_true',
                      help='Enable URL encoding')
    parser.add_argument('--validate-urls', action='store_true',
                      help='Check if URLs are accessible')

    # 引用键选项
    parser.add_argument('--auto-keys', action='store_true',
                      help='Automatically generate citation keys')
    parser.add_argument('--key-format',
                      help='Format for citation keys (e.g., "[auth][year][title:3]")')

    # 排序和重复项处理
    parser.add_argument('--duplicate-check', choices=['key', 'doi', 'title', 'all'],
                      help='Duplicate checking method')
    parser.add_argument('--merge-strategy', choices=['combine', 'overwrite', 'first', 'last'],
                      help='Strategy for merging duplicates')
    parser.add_argument('--sort-entries', choices=['key', 'year', 'author', 'none'],
                      help='Sort entries by: key (citation key), year, author, or none (preserve original order)')

    # 其他选项
    parser.add_argument('--header', action='store_true',
                      help='Enable header comments with processing information')

    args = parser.parse_args()
    
    # 处理字段替换参数
    field_replacements = {}
    if args.replace_fields:
        for replacement in args.replace_fields.split(','):
            old_field, new_field = replacement.split(':')
            field_replacements[old_field.strip()] = new_field.strip()
    
    # 只包含实际指定的选项
    options = {
        'use_tabs': not args.use_spaces if args.use_spaces is not None else True,
        'field_replacements': field_replacements,
        'field_order': args.field_order,
    }
    
    # 只有当参数被明确指定时才添加到选项中
    # 格式化选项
    if args.align is not None:
        options['align_values'] = args.align
    if args.double_braces:
        options['double_braces'] = True
    if args.entry_spacing is not None:
        options['entry_spacing'] = args.entry_spacing
    # 字段处理选项
    if args.omit:
        options['omit_fields'] = [field.strip() for field in args.omit.split(',') if field.strip()]
    if args.sort_fields:
        options['sort_fields'] = True
    # 作者处理选项
    if args.max_authors is not None:
        options['max_authors'] = args.max_authors
    # URL处理选项
    if args.encode_urls:
        options['encode_urls'] = True
    if args.validate_urls:
        options['validate_urls'] = True
    # 引用键选项
    if args.auto_keys:
        options['auto_generate_keys'] = True
    if args.key_format:
        options['key_format'] = args.key_format
    # 排序和重复项处理
    if args.duplicate_check:
        options['duplicate_check'] = args.duplicate_check
    if args.merge_strategy:
        options['merge_duplicates'] = True
        options['merge_strategy'] = args.merge_strategy
    # 其他选项
    if args.header:
        options['header'] = True

    
    # 处理文件或目录
    if os.path.isdir(args.input):
        process_directory(args.input, options)
    else:
        processor = BibTidy(options)
        processor.process_file(args.input, args.output)
        print(f"Processing complete: {args.input}")
        if args.output:
            print(f"Saved to: {args.output}")

if __name__ == "__main__":
    main()