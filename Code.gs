/**
 * Google Sheets dashboard for YouTube + RSS monitoring with AI scoring and Telegram weekly digest.
 *
 * How to use:
 * 1. Create a blank Google Sheet.
 * 2. Extensions -> Apps Script -> paste this file.
 * 3. Run setupDashboard().
 * 4. Fill API keys and Telegram settings in the Settings sheet.
 * 5. Add or disable sources in the Sources sheet.
 * 6. Run refreshAll() once, then installTriggers().
 */

const SHEETS = {
  dashboard: 'Dashboard',
  settings: 'Settings',
  sources: 'Sources',
  rawRss: 'Raw RSS',
  rawYoutube: 'Raw YouTube',
  scored: 'Scored Content',
  weekly: 'Weekly Top 5',
  telegram: 'Telegram Queue',
  logs: 'Logs'
};

const HEADERS = {
  settings: ['Key', 'Value', 'Description'],
  sources: ['Type', 'Name', 'URL_OR_ID', 'Query', 'Enabled', 'Weight', 'Notes', 'LastFetched'],
  rawRss: ['Source', 'Title', 'Link', 'PublishedAt', 'Summary', 'FetchedAt', 'ContentHash', 'Status'],
  rawYoutube: ['Source', 'VideoId', 'Title', 'URL', 'PublishedAt', 'ChannelTitle', 'Description', 'FetchedAt', 'ContentHash', 'Status'],
  scored: ['Hash', 'SourceType', 'Source', 'Title', 'URL', 'PublishedAt', 'Summary', 'Score', 'ImpactAreas', 'WhyItMatters', 'RecommendedAction', 'Urgency', 'Confidence', 'ScoredAt'],
  weekly: ['WeekStart', 'Rank', 'Score', 'Title', 'URL', 'Source', 'WhyItMatters', 'RecommendedAction', 'SentToTelegram', 'SentAt'],
  telegram: ['CreatedAt', 'Status', 'ChatId', 'Message', 'SentAt', 'Error'],
  logs: ['Timestamp', 'Level', 'Step', 'Message', 'Details']
};

function setupDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  createSheet_(ss, SHEETS.dashboard, []);
  createSheet_(ss, SHEETS.settings, HEADERS.settings);
  createSheet_(ss, SHEETS.sources, HEADERS.sources);
  createSheet_(ss, SHEETS.rawRss, HEADERS.rawRss);
  createSheet_(ss, SHEETS.rawYoutube, HEADERS.rawYoutube);
  createSheet_(ss, SHEETS.scored, HEADERS.scored);
  createSheet_(ss, SHEETS.weekly, HEADERS.weekly);
  createSheet_(ss, SHEETS.telegram, HEADERS.telegram);
  createSheet_(ss, SHEETS.logs, HEADERS.logs);

  seedSettings_();
  seedSources_();
  buildDashboard_();
  applyFormatting_();
  log_('INFO', 'setup', 'Dashboard initialized', 'Fill Settings, then run refreshAll().');
}

function refreshAll() {
  fetchRssSources();
  fetchYouTubeSources();
  scoreNewContent();
  updateWeeklyTop5();
  buildDashboard_();
}

function installTriggers() {
  clearTriggers_();
  const settings = getSettings_();
  const refreshHours = Number(settings.REFRESH_EVERY_HOURS || 6);
  ScriptApp.newTrigger('refreshAll').timeBased().everyHours(Math.max(1, refreshHours)).create();
  ScriptApp.newTrigger('sendWeeklyDigestToTelegram')
    .timeBased()
    .onWeekDay(dayToScriptDay_(settings.WEEKLY_DIGEST_DAY || 'MONDAY'))
    .atHour(Number(settings.WEEKLY_DIGEST_HOUR || 9))
    .create();
  log_('INFO', 'triggers', 'Triggers installed', `refreshEveryHours=${refreshHours}`);
}

function clearTriggers_() {
  ScriptApp.getProjectTriggers().forEach(trigger => ScriptApp.deleteTrigger(trigger));
}

function fetchRssSources() {
  const sources = getEnabledSources_().filter(s => s.Type === 'RSS');
  const existing = getExistingHashes_(SHEETS.rawRss, 7);
  let inserted = 0;

  sources.forEach(source => {
    try {
      const response = UrlFetchApp.fetch(source.URL_OR_ID, {
        muteHttpExceptions: true,
        followRedirects: true,
        headers: {'User-Agent': 'GoogleAppsScript RSS Monitor'}
      });
      const code = response.getResponseCode();
      if (code < 200 || code >= 300) {
        log_('WARN', 'rss', `RSS fetch failed for ${source.Name}`, `HTTP ${code}: ${source.URL_OR_ID}`);
        return;
      }
      const xml = XmlService.parse(response.getContentText());
      const items = parseFeedItems_(xml);
      const rows = [];
      items.forEach(item => {
        const hash = digest_([source.Name, item.link, item.title].join('|'));
        if (existing.has(hash)) return;
        existing.add(hash);
        rows.push([
          source.Name,
          item.title,
          item.link,
          item.publishedAt,
          item.summary,
          new Date(),
          hash,
          'NEW'
        ]);
      });
      appendRows_(SHEETS.rawRss, rows);
      inserted += rows.length;
      markSourceFetched_(source.rowNumber);
    } catch (error) {
      log_('ERROR', 'rss', `RSS parse failed for ${source.Name}`, String(error));
    }
  });

  log_('INFO', 'rss', 'RSS refresh completed', `Inserted ${inserted} new items.`);
}

function fetchYouTubeSources() {
  const settings = getSettings_();
  const apiKey = settings.YOUTUBE_API_KEY;
  if (!apiKey) {
    log_('WARN', 'youtube', 'Missing YOUTUBE_API_KEY', 'Set it in Settings to enable YouTube ingestion.');
    return;
  }

  const sources = getEnabledSources_().filter(s => s.Type === 'YOUTUBE_SEARCH' || s.Type === 'YOUTUBE_CHANNEL');
  const existing = getExistingHashes_(SHEETS.rawYoutube, 9);
  const maxResults = Number(settings.YOUTUBE_MAX_RESULTS_PER_SOURCE || 10);
  const daysBack = Number(settings.LOOKBACK_DAYS || 10);
  const publishedAfter = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000).toISOString();
  let inserted = 0;

  sources.forEach(source => {
    try {
      const params = {
        key: apiKey,
        part: 'snippet',
        type: 'video',
        order: 'date',
        maxResults: String(Math.min(50, maxResults)),
        publishedAfter,
        regionCode: settings.YOUTUBE_REGION_CODE || 'UA',
        relevanceLanguage: settings.YOUTUBE_RELEVANCE_LANGUAGE || 'uk'
      };
      if (source.Type === 'YOUTUBE_CHANNEL') {
        params.channelId = source.URL_OR_ID;
      } else {
        params.q = source.Query || source.URL_OR_ID;
      }

      const url = 'https://www.googleapis.com/youtube/v3/search?' + toQueryString_(params);
      const response = UrlFetchApp.fetch(url, {muteHttpExceptions: true});
      const code = response.getResponseCode();
      if (code < 200 || code >= 300) {
        log_('WARN', 'youtube', `YouTube fetch failed for ${source.Name}`, response.getContentText().slice(0, 500));
        return;
      }

      const data = JSON.parse(response.getContentText());
      const rows = [];
      (data.items || []).forEach(item => {
        const videoId = item.id && item.id.videoId;
        if (!videoId) return;
        const snippet = item.snippet || {};
        const link = `https://www.youtube.com/watch?v=${videoId}`;
        const hash = digest_([source.Name, videoId, snippet.title].join('|'));
        if (existing.has(hash)) return;
        existing.add(hash);
        rows.push([
          source.Name,
          videoId,
          snippet.title || '',
          link,
          snippet.publishedAt || '',
          snippet.channelTitle || '',
          snippet.description || '',
          new Date(),
          hash,
          'NEW'
        ]);
      });
      appendRows_(SHEETS.rawYoutube, rows);
      inserted += rows.length;
      markSourceFetched_(source.rowNumber);
    } catch (error) {
      log_('ERROR', 'youtube', `YouTube fetch failed for ${source.Name}`, String(error));
    }
  });

  log_('INFO', 'youtube', 'YouTube refresh completed', `Inserted ${inserted} new videos.`);
}

function scoreNewContent() {
  const settings = getSettings_();
  const sourceWeights = {};
  getEnabledSources_().forEach(source => sourceWeights[source.Name] = source.Weight || 1);
  const existingScored = getExistingHashes_(SHEETS.scored, 1);
  const rssRows = getDataRows_(SHEETS.rawRss).map(row => ({
    sourceType: 'RSS',
    source: row[0],
    title: row[1],
    url: row[2],
    publishedAt: row[3],
    summary: row[4],
    hash: row[6]
  }));
  const ytRows = getDataRows_(SHEETS.rawYoutube).map(row => ({
    sourceType: 'YouTube',
    source: row[0],
    title: row[2],
    url: row[3],
    publishedAt: row[4],
    summary: row[6],
    hash: row[8]
  }));

  const maxItems = Number(settings.MAX_ITEMS_TO_SCORE_PER_RUN || 40);
  const candidates = rssRows.concat(ytRows)
    .filter(item => item.hash && !existingScored.has(item.hash))
    .sort((a, b) => new Date(b.publishedAt || 0) - new Date(a.publishedAt || 0))
    .slice(0, maxItems);

  const rows = [];
  candidates.forEach(item => {
    try {
      const score = getAiScore_(item, settings);
      score.score = applySourceWeight_(score.score, sourceWeights[item.source] || 1);
      rows.push([
        item.hash,
        item.sourceType,
        item.source,
        item.title,
        item.url,
        item.publishedAt,
        item.summary,
        score.score,
        (score.impact_areas || []).join(', '),
        score.why_it_matters,
        score.recommended_action,
        score.urgency,
        score.confidence,
        new Date()
      ]);
    } catch (error) {
      log_('ERROR', 'scoring', `Scoring failed: ${item.title}`, String(error));
    }
  });

  appendRows_(SHEETS.scored, rows);
  log_('INFO', 'scoring', 'Scoring completed', `Scored ${rows.length} items.`);
}

function applySourceWeight_(score, weight) {
  const weighted = Number(score) + (Number(weight || 1) - 1);
  return Math.max(1, Math.min(5, Math.round(weighted)));
}

function updateWeeklyTop5() {
  const rows = getDataRows_(SHEETS.scored);
  const weekStart = getWeekStart_(new Date());
  const existingWeekRows = getDataRows_(SHEETS.weekly).filter(r => String(r[0]) !== String(weekStart));
  const candidates = rows
    .filter(row => row[7])
    .filter(row => new Date(row[5] || row[13]) >= weekStart)
    .sort((a, b) => Number(b[7]) - Number(a[7]) || new Date(b[13]) - new Date(a[13]))
    .slice(0, 5)
    .map((row, index) => [
      weekStart,
      index + 1,
      row[7],
      row[3],
      row[4],
      row[2],
      row[9],
      row[10],
      '',
      ''
    ]);

  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.weekly);
  sheet.clearContents();
  sheet.getRange(1, 1, 1, HEADERS.weekly.length).setValues([HEADERS.weekly]);
  appendRows_(SHEETS.weekly, existingWeekRows.concat(candidates));
  applyFormatting_();
}

function sendWeeklyDigestToTelegram() {
  updateWeeklyTop5();
  const settings = getSettings_();
  const token = settings.TELEGRAM_BOT_TOKEN;
  const chatId = settings.TELEGRAM_CHAT_ID;
  if (!token || !chatId) {
    log_('WARN', 'telegram', 'Telegram settings missing', 'Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.');
    return;
  }

  const weekStart = getWeekStart_(new Date());
  const rows = getDataRows_(SHEETS.weekly)
    .filter(row => String(row[0]) === String(weekStart))
    .sort((a, b) => Number(a[1]) - Number(b[1]));
  if (!rows.length) {
    log_('INFO', 'telegram', 'No weekly items to send', String(weekStart));
    return;
  }

  const message = buildTelegramDigest_(rows, settings);
  enqueueTelegram_(chatId, message);
  flushTelegramQueue();

  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.weekly);
  const all = sheet.getDataRange().getValues();
  for (let i = 1; i < all.length; i++) {
    if (String(all[i][0]) === String(weekStart)) {
      sheet.getRange(i + 1, 9).setValue('YES');
      sheet.getRange(i + 1, 10).setValue(new Date());
    }
  }
}

function flushTelegramQueue() {
  const settings = getSettings_();
  const token = settings.TELEGRAM_BOT_TOKEN;
  if (!token) return;

  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.telegram);
  const values = sheet.getDataRange().getValues();
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    if (row[1] === 'SENT') continue;
    try {
      const payload = {
        chat_id: row[2],
        text: row[3],
        parse_mode: 'HTML',
        disable_web_page_preview: true
      };
      const response = UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'post',
        contentType: 'application/json',
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      });
      const code = response.getResponseCode();
      if (code >= 200 && code < 300) {
        sheet.getRange(i + 1, 2).setValue('SENT');
        sheet.getRange(i + 1, 5).setValue(new Date());
        sheet.getRange(i + 1, 6).setValue('');
      } else {
        sheet.getRange(i + 1, 2).setValue('ERROR');
        sheet.getRange(i + 1, 6).setValue(response.getContentText().slice(0, 1000));
      }
    } catch (error) {
      sheet.getRange(i + 1, 2).setValue('ERROR');
      sheet.getRange(i + 1, 6).setValue(String(error));
    }
  }
}

function getAiScore_(item, settings) {
  const provider = String(settings.AI_PROVIDER || 'HEURISTIC').toUpperCase();
  if (provider === 'OPENAI' && settings.OPENAI_API_KEY) return scoreWithOpenAI_(item, settings);
  if (provider === 'GEMINI' && settings.GEMINI_API_KEY) return scoreWithGemini_(item, settings);
  return heuristicScore_(item);
}

function scoreWithOpenAI_(item, settings) {
  const payload = {
    model: settings.OPENAI_MODEL || 'gpt-4o-mini',
    response_format: {type: 'json_object'},
    messages: [
      {role: 'system', content: scoringSystemPrompt_()},
      {role: 'user', content: JSON.stringify(item)}
    ],
    temperature: 0.2
  };
  const response = UrlFetchApp.fetch('https://api.openai.com/v1/chat/completions', {
    method: 'post',
    contentType: 'application/json',
    headers: {Authorization: `Bearer ${settings.OPENAI_API_KEY}`},
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error(response.getContentText());
  }
  const data = JSON.parse(response.getContentText());
  return normalizeScore_(JSON.parse(data.choices[0].message.content));
}

function scoreWithGemini_(item, settings) {
  const model = settings.GEMINI_MODEL || 'gemini-1.5-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${settings.GEMINI_API_KEY}`;
  const payload = {
    contents: [{
      role: 'user',
      parts: [{text: scoringSystemPrompt_() + '\n\nReturn strict JSON only.\n\nItem:\n' + JSON.stringify(item)}]
    }],
    generationConfig: {temperature: 0.2, responseMimeType: 'application/json'}
  };
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
    throw new Error(response.getContentText());
  }
  const data = JSON.parse(response.getContentText());
  const text = data.candidates[0].content.parts[0].text;
  return normalizeScore_(JSON.parse(text));
}

function heuristicScore_(item) {
  const text = `${item.title} ${item.summary}`.toLowerCase();
  const rules = [
    {re: /(google|seo|пошук|выдач|алгоритм|core update|merchant center|shopping)/i, points: 2, area: 'SEO/Google visibility'},
    {re: /(e-?commerce|онлайн.?торг|маркетплейс|prom|rozetka|shopify|checkout)/i, points: 2, area: 'E-commerce channels'},
    {re: /(мебл|матрац|матрас|home|інтер'єр|ремонт|спальн|диван)/i, points: 2, area: 'Category demand'},
    {re: /(логіст|достав|пальн|склад|імпорт|курс|інфляц|ціни|подат)/i, points: 1, area: 'Costs/supply chain'},
    {re: /(реклама|meta|facebook|instagram|google ads|tiktok|cpc|маркетинг)/i, points: 1, area: 'Paid acquisition'},
    {re: /(закон|штраф|регул|персональн|дані|податк|споживач)/i, points: 1, area: 'Regulatory/reputation'}
  ];
  let score = 1;
  const areas = [];
  rules.forEach(rule => {
    if (rule.re.test(text)) {
      score += rule.points;
      areas.push(rule.area);
    }
  });
  score = Math.max(1, Math.min(5, score));
  return normalizeScore_({
    score,
    impact_areas: areas.length ? areas : ['General monitoring'],
    why_it_matters: score >= 4
      ? 'Potential direct impact on search visibility, demand, acquisition cost, or furniture/mattress category operations.'
      : 'Monitor for context; impact appears indirect or low urgency.',
    recommended_action: score >= 4
      ? 'Review within 24 hours and decide whether to adjust SEO content, ads, pricing, logistics, or product positioning.'
      : 'Keep in weekly monitoring unless the topic repeats across sources.',
    urgency: score >= 4 ? 'High' : score >= 3 ? 'Medium' : 'Low',
    confidence: 'Medium'
  });
}

function scoringSystemPrompt_() {
  return [
    'You are an e-commerce strategy analyst for a Ukraine-based mattress/furniture business.',
    'Score each news/video item from 1 to 5 by practical business impact.',
    '5 = immediate reaction needed this week; 4 = high strategic relevance; 3 = monitor and maybe adapt; 2 = weak indirect relevance; 1 = ignore.',
    'Prioritize SEO/search ranking, Google algorithm and Merchant Center changes, marketplace shifts, furniture/mattress demand, logistics, import costs, ad platform changes, consumer trust, regulation, competitor moves, and Ukrainian retail/e-commerce macro signals.',
    'Return JSON with: score number, impact_areas string array, why_it_matters string, recommended_action string, urgency Low|Medium|High, confidence Low|Medium|High.',
    'Keep why_it_matters and recommended_action concise and actionable.'
  ].join('\n');
}

function normalizeScore_(obj) {
  const score = Math.max(1, Math.min(5, Number(obj.score || 1)));
  return {
    score,
    impact_areas: Array.isArray(obj.impact_areas) ? obj.impact_areas : [String(obj.impact_areas || 'General')],
    why_it_matters: String(obj.why_it_matters || ''),
    recommended_action: String(obj.recommended_action || ''),
    urgency: String(obj.urgency || (score >= 4 ? 'High' : score >= 3 ? 'Medium' : 'Low')),
    confidence: String(obj.confidence || 'Medium')
  };
}

function parseFeedItems_(xml) {
  const root = xml.getRootElement();
  const name = root.getName().toLowerCase();
  if (name === 'rss') {
    const channel = root.getChild('channel');
    return channel.getChildren('item').map(item => ({
      title: childText_(item, 'title'),
      link: childText_(item, 'link'),
      publishedAt: childText_(item, 'pubDate'),
      summary: stripHtml_(childText_(item, 'description'))
    }));
  }
  if (name === 'feed') {
    const ns = root.getNamespace();
    return root.getChildren('entry', ns).map(entry => {
      const linkEl = entry.getChildren('link', ns).find(l => l.getAttribute('href'));
      return {
        title: childText_(entry, 'title', ns),
        link: linkEl ? linkEl.getAttribute('href').getValue() : '',
        publishedAt: childText_(entry, 'updated', ns) || childText_(entry, 'published', ns),
        summary: stripHtml_(childText_(entry, 'summary', ns) || childText_(entry, 'content', ns))
      };
    });
  }
  return [];
}

function buildTelegramDigest_(rows, settings) {
  const title = settings.TELEGRAM_DIGEST_TITLE || 'Weekly e-commerce signals: матрасы/мебель';
  const lines = [`<b>${escapeHtml_(title)}</b>`, '', 'Топ-5 событий недели, требующих реакции:'];
  rows.forEach(row => {
    lines.push('');
    lines.push(`<b>${row[1]}. ${escapeHtml_(row[3])}</b>`);
    lines.push(`Score: ${row[2]}/5 | Source: ${escapeHtml_(row[5])}`);
    lines.push(`Why: ${escapeHtml_(row[6])}`);
    lines.push(`Action: ${escapeHtml_(row[7])}`);
    lines.push(row[4]);
  });
  lines.push('');
  lines.push('Обнови стратегию SEO/контента/рекламы, если несколько сигналов повторяются в разных источниках.');
  return lines.join('\n').slice(0, 3900);
}

function buildDashboard_() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.dashboard);
  sheet.clear();
  const values = [
    ['E-commerce Media Radar', 'YouTube + RSS + AI scoring'],
    ['Last refresh', '=NOW()'],
    ['Scored items', `=COUNTA('${SHEETS.scored}'!A2:A)`],
    ['High impact items score >= 4', `=COUNTIF('${SHEETS.scored}'!H2:H,">=4")`],
    ['Weekly top source count', `=COUNTA('${SHEETS.weekly}'!A2:A)`],
    [''],
    ['Top 5 this week'],
    ['Rank', 'Score', 'Title', 'Source', 'Action', 'URL'],
    ['=IFERROR(QUERY(\'' + SHEETS.weekly + '\'!A:J,"select B,C,D,F,H,E where A is not null order by B asc limit 5",1),"Run updateWeeklyTop5()")']
  ];
  sheet.getRange(1, 1, values.length, 2).setValues(values.map(r => [r[0] || '', r[1] || '']));
  sheet.getRange('A1:B1').merge().setFontSize(18).setFontWeight('bold').setBackground('#01696F').setFontColor('#FFFFFF');
  sheet.setColumnWidth(1, 220);
  sheet.setColumnWidth(2, 760);
}

function seedSettings_() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.settings);
  if (sheet.getLastRow() > 1) return;
  appendRows_(SHEETS.settings, [
    ['YOUTUBE_API_KEY', '', 'Google Cloud YouTube Data API v3 key.'],
    ['AI_PROVIDER', 'HEURISTIC', 'HEURISTIC, OPENAI, or GEMINI.'],
    ['OPENAI_API_KEY', '', 'Used only if AI_PROVIDER=OPENAI.'],
    ['OPENAI_MODEL', 'gpt-4o-mini', 'OpenAI model for JSON scoring.'],
    ['GEMINI_API_KEY', '', 'Used only if AI_PROVIDER=GEMINI.'],
    ['GEMINI_MODEL', 'gemini-1.5-flash', 'Gemini model for JSON scoring.'],
    ['TELEGRAM_BOT_TOKEN', '', 'Bot token from @BotFather. Keep private.'],
    ['TELEGRAM_CHAT_ID', '', 'Channel ID or @channelusername. Bot must be admin with post rights.'],
    ['TELEGRAM_DIGEST_TITLE', 'Weekly e-commerce signals: матрасы/мебель', 'Telegram digest header.'],
    ['TIMEZONE', 'Europe/Kiev', 'Project timezone.'],
    ['REFRESH_EVERY_HOURS', '6', 'RSS/YouTube refresh cadence.'],
    ['WEEKLY_DIGEST_DAY', 'MONDAY', 'MONDAY...SUNDAY.'],
    ['WEEKLY_DIGEST_HOUR', '9', 'Hour in script timezone.'],
    ['LOOKBACK_DAYS', '10', 'YouTube publishedAfter window.'],
    ['YOUTUBE_MAX_RESULTS_PER_SOURCE', '10', 'Max YouTube results per source per run.'],
    ['YOUTUBE_REGION_CODE', 'UA', 'YouTube region code.'],
    ['YOUTUBE_RELEVANCE_LANGUAGE', 'uk', 'YouTube relevance language.'],
    ['MAX_ITEMS_TO_SCORE_PER_RUN', '40', 'Scoring batch size per refresh.'],
    ['MIN_SCORE_TO_NOTIFY', '4', 'Reserved for future immediate alerts.']
  ]);
}

function seedSources_() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEETS.sources);
  if (sheet.getLastRow() > 1) return;
  appendRows_(SHEETS.sources, [
    ['RSS', 'AIN.ua', 'https://ain.ua/feed/', '', 'TRUE', '1.2', 'Tech/startups/e-commerce signals', ''],
    ['RSS', 'DOU', 'https://dou.ua/lenta/feed/', '', 'TRUE', '1.0', 'Tech labor, platforms, Ukrainian IT', ''],
    ['RSS', 'Vector', 'https://vctr.media/feed/', '', 'TRUE', '1.0', 'Business, tech, marketing', ''],
    ['RSS', 'Економічна правда', 'https://www.epravda.com.ua/rss/', '', 'TRUE', '1.1', 'Economy, regulation, macro', ''],
    ['RSS', 'RAU', 'https://rau.ua/feed/', '', 'TRUE', '1.3', 'Retail Association of Ukraine', ''],
    ['RSS', 'MMR', 'https://mmr.ua/feed', '', 'TRUE', '0.9', 'Marketing and media', ''],
    ['RSS', 'MC.today', 'https://mc.today/feed/', '', 'TRUE', '1.0', 'Entrepreneurship and tech', ''],
    ['RSS', 'Українська правда', 'https://www.pravda.com.ua/rss/view_news/', '', 'FALSE', '0.6', 'General news; enable if needed', ''],
    ['YOUTUBE_SEARCH', 'UA e-commerce SEO', '', 'e-commerce Україна SEO Google Merchant Center маркетплейс', 'TRUE', '1.4', 'Search query', ''],
    ['YOUTUBE_SEARCH', 'Furniture mattress demand', '', 'меблі матраци Україна попит ціни доставка', 'TRUE', '1.5', 'Category query', ''],
    ['YOUTUBE_SEARCH', 'Retail Ukraine', '', 'ритейл Україна e-commerce логістика маркетплейси', 'TRUE', '1.2', 'Retail/e-commerce query', ''],
    ['YOUTUBE_SEARCH', 'Google SEO updates', '', 'Google update SEO e-commerce merchant center', 'TRUE', '1.3', 'Search visibility query', '']
  ]);
}

function createSheet_(ss, name, headers) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (headers && headers.length) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#01696F').setFontColor('#FFFFFF');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function applyFormatting_() {
  const ss = SpreadsheetApp.getActive();
  Object.values(SHEETS).forEach(name => {
    const sheet = ss.getSheetByName(name);
    if (!sheet) return;
    sheet.autoResizeColumns(1, Math.min(10, Math.max(1, sheet.getLastColumn())));
  });
  const scored = ss.getSheetByName(SHEETS.scored);
  if (scored && scored.getLastRow() > 1) {
    const range = scored.getRange(2, 8, Math.max(1, scored.getMaxRows() - 1), 1);
    const rules = [
      SpreadsheetApp.newConditionalFormatRule().whenNumberGreaterThanOrEqualTo(4).setBackground('#DDEFE8').setFontColor('#1B474D').setRanges([range]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenNumberLessThanOrEqualTo(2).setBackground('#F4E4DF').setFontColor('#A84B2F').setRanges([range]).build()
    ];
    scored.setConditionalFormatRules(rules);
  }
}

function getSettings_() {
  const rows = getDataRows_(SHEETS.settings);
  const settings = {};
  rows.forEach(row => settings[String(row[0]).trim()] = row[1]);
  return settings;
}

function getEnabledSources_() {
  return getDataRows_(SHEETS.sources).map((row, index) => ({
    rowNumber: index + 2,
    Type: String(row[0]).trim(),
    Name: String(row[1]).trim(),
    URL_OR_ID: String(row[2]).trim(),
    Query: String(row[3]).trim(),
    Enabled: String(row[4]).toUpperCase() === 'TRUE',
    Weight: Number(row[5] || 1),
    Notes: row[6]
  })).filter(source => source.Enabled);
}

function getDataRows_(sheetName) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() < 2) return [];
  return sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).getValues();
}

function appendRows_(sheetName, rows) {
  if (!rows || !rows.length) return;
  const sheet = SpreadsheetApp.getActive().getSheetByName(sheetName);
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
}

function getExistingHashes_(sheetName, columnIndex) {
  const rows = getDataRows_(sheetName);
  return new Set(rows.map(row => String(row[columnIndex - 1] || '')).filter(Boolean));
}

function markSourceFetched_(rowNumber) {
  SpreadsheetApp.getActive().getSheetByName(SHEETS.sources).getRange(rowNumber, 8).setValue(new Date());
}

function log_(level, step, message, details) {
  appendRows_(SHEETS.logs, [[new Date(), level, step, message, details || '']]);
}

function enqueueTelegram_(chatId, message) {
  appendRows_(SHEETS.telegram, [[new Date(), 'PENDING', chatId, message, '', '']]);
}

function childText_(element, name, ns) {
  const child = ns ? element.getChild(name, ns) : element.getChild(name);
  return child ? child.getText() : '';
}

function stripHtml_(html) {
  return String(html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 1000);
}

function digest_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text)
    .map(b => ('0' + (b & 0xFF).toString(16)).slice(-2))
    .join('');
}

function toQueryString_(params) {
  return Object.keys(params)
    .filter(k => params[k] !== undefined && params[k] !== '')
    .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join('&');
}

function getWeekStart_(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const start = new Date(d.setDate(diff));
  start.setHours(0, 0, 0, 0);
  return start;
}

function dayToScriptDay_(day) {
  const map = {
    MONDAY: ScriptApp.WeekDay.MONDAY,
    TUESDAY: ScriptApp.WeekDay.TUESDAY,
    WEDNESDAY: ScriptApp.WeekDay.WEDNESDAY,
    THURSDAY: ScriptApp.WeekDay.THURSDAY,
    FRIDAY: ScriptApp.WeekDay.FRIDAY,
    SATURDAY: ScriptApp.WeekDay.SATURDAY,
    SUNDAY: ScriptApp.WeekDay.SUNDAY
  };
  return map[String(day).toUpperCase()] || ScriptApp.WeekDay.MONDAY;
}

function escapeHtml_(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
