import React, { useEffect, useState } from "react";
import {
  DataComponent, DataTable, Dropdown, EvidenceChart, Filters, MetricCard, SectionHeader,
  SortableItem, SortableRegion, useDashboardTabs, useDataApp, useSectionFilters,
} from "../../data-app-public.jsx";
import { worldCountries } from "./world-geography.js";

const tabs = [
  { id: "industry", label: "Industry", filterIds: [] },
  { id: "audiobooks", label: "Audiobooks", filterIds: [] },
  { id: "reading", label: "Reading", filterIds: [] },
  { id: "formats", label: "Formats", filterIds: [] },
  { id: "genres", label: "Genres", filterIds: [] },
  { id: "coverage", label: "Coverage", filterIds: [] },
];
const RATE = "Participation (%)";
const PREFERENCE = "Listeners selecting option (%)";
const fmt = value => Number.isFinite(value) ? `${value.toFixed(1)}%` : "Unavailable";
const fmtChecked = value => {
  if (!value) return "Check record pending";
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium", timeStyle: "short", timeZone: "UTC",
  }).format(parsed) : String(value);
};
const rateRows = rows => rows.map(row => ({ ...row, [RATE]: row.participation }));
const surveyYearChoices = rows => [...new Set(rows.map(row => row.year).filter(Number.isFinite))].sort((a, b) => b - a).map(String);
const bar = (x, extra = {}) => ({ type: "horizontalBar", x, y: RATE, startAtZero: true,
  stackable: false, valueDecimals: 1, showXAxisLabel: false, showYAxisLabel: false, ...extra });
const formatColors = { Print: "var(--chart-1)", Ebook: "var(--chart-3)", Audiobook: "var(--chart-2)" };
const statusColors = {
  "Data extracted": "#25897e", "Reviewed, missing result": "#c68038",
  "Public source documented": "#6285b0", "Candidate only": "#b39a64", "Not researched": "#dde3e7",
};
function Note({ children, tone = "default" }) {
  return <p className="atlas-note" data-tone={tone}>{children}</p>;
}
function Block({ id, title, span = 6, kind = "chart", children, ...placementProps }) {
  return <SortableItem {...placementProps} id={id} label={title} kind={kind} span={span}>{children}</SortableItem>;
}
function Plot({ id, queryId, title, rows, spec, height = 290, children, ...props }) {
  return <EvidenceChart variant="card" id={id} queryId={queryId} title={title}
    spec={spec} rows={rateRows(rows)} sourceRows={rows} height={height} {...props}>{children}</EvidenceChart>;
}
function SourceLink({ url, children }) {
  return <a href={url} target="_blank" rel="noreferrer">{children}</a>;
}

export function DashboardContent() {
  const { activeTabId } = useDashboardTabs(tabs);
  const tab = tabs.some(item => item.id === activeTabId) ? activeTabId : "industry";
  return <article className="atlas-dashboard">
    {tab === "industry" && <Industry />}
    {tab === "audiobooks" && <Audiobooks />}
    {tab === "reading" && <Reading />}
    {tab === "formats" && <Formats />}
    {tab === "genres" && <Genres />}
    {tab === "coverage" && <Coverage />}
  </article>;
}

function Industry() {
  const { queries, reviewedRows } = useDataApp();
  const companies = queries.companies ? reviewedRows("companies", ["company_id"]) : [];
  const originalSeries = (queries.industry_metrics?.rows ?? []).filter(row => row.year >= 2022);
  const initialSeries = originalSeries.find(row => /audio/i.test(row.metric))?.series_id ?? originalSeries[0]?.series_id ?? "all";
  const countries = [...new Set(originalSeries.map(row => row.country).filter(Boolean))].sort();
  const seriesLabels = Object.fromEntries(originalSeries.map(row => [row.series_id, `${row.metric} (${row.unit})`]));
  const scope = useSectionFilters([
    { id: "series", label: "Revenue measure", field: "series_id", defaultValue: initialSeries, queryIds: ["industry_metrics"], choiceLabels: seriesLabels },
  ], {}, { rowId: "atlas:industry:series", componentIds: ["industry-market-series"], label: "Book industry revenue filters" });
  const selectedSeries = originalSeries.find(row => row.series_id === scope.values.series);
  const selectedCountry = selectedSeries?.country ?? "all";
  const countrySeries = originalSeries.filter(row => row.country === selectedCountry);
  const measureChoices = [...new Set(countrySeries.map(row => row.series_id))];
  const revenueControls = <Filters {...scope.filterProps} filters={[]}>
    <Dropdown label="Country" showLabel value={selectedCountry} choices={countries}
      allLabel="Choose one country" onChange={country => {
        const available = originalSeries.filter(row => row.country === country);
        const preferred = available.find(row => row.metric === selectedSeries?.metric)
          ?? available.find(row => /audio/i.test(row.metric)) ?? available[0];
        scope.setFilter("series", preferred?.series_id ?? "all");
      }} />
    <Dropdown label="Revenue measure" showLabel value={scope.values.series} choices={measureChoices}
      choiceLabels={seriesLabels} allLabel="Choose one revenue measure"
      onChange={value => scope.setFilter("series", value)} />
  </Filters>;
  const scoped = scope.componentProps("industry_metrics", ["series_id", "year"]);
  const observations = scope.values.series === "all" ? [] : scoped.sourceRows.filter(row => row.year >= 2022).sort((a, b) => a.year - b.year);
  const latest = observations.at(-1);
  const sourceCheck = (queries.data_freshness?.rows ?? []).find(row => row.source_id === latest?.source_id);
  const hasVintageBreak = /as_published/.test(latest?.series_id ?? "");
  const seriesTitle = latest ? `${latest.country}: ${latest.metric} (${latest.unit})${hasVintageBreak ? " · as published" : ""}` : "Sales and revenue by year";
  const unit = latest?.unit ?? "source unit";
  const valueField = `Value (${unit === "percent" || unit === "%" ? "%" : unit})`;
  const plottedRows = observations.map(row => ({ ...row, "Observation year": String(row.year), [valueField]: row.value }));
  const companyColumns = [
    { field: "company", label: "Company", presentation: "identity", secondaryField: "parent_company" },
    { field: "formats", label: "Book formats" },
    { field: "business_model", label: "Business model" },
    { field: "geographic_scope", label: "Geographic scope" },
    { field: "public_data_status", label: "Public data available" },
    { field: "notes", label: "Scope and limits" },
    { field: "source_url", label: "Original source", renderCell: value => value ? <SourceLink url={value}>Open source ↗</SourceLink> : "Not reviewed" },
  ];
  return <>
    <Note>Public book industry money figures include publisher revenue, retail turnover and other reported sales values. Reading and Audiobooks show audience measures.</Note>
    <Note>{countries.length ? `Reviewed monetary evidence covers ${countries.length} countries. Worldwide coverage is incomplete. Choose a country and revenue measure below.` : "Reviewed industry figures are being prepared."} The international company register follows.</Note>
    <SortableRegion id="atlas:industry:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:industry:series", items: ["industry-market-series"], header: <SectionHeader id="industry-series-heading" title="Book industry sales and revenue" filters={revenueControls} /> },
      { id: "atlas:industry:companies", items: ["industry-company-register"], header: <SectionHeader id="industry-companies-heading" title="Company landscape and public data" /> },
    ]}>
      <Block id="industry-market-series" title="Sales and revenue by year" span={12}>
        {queries.industry_metrics ? <EvidenceChart variant="card" id="industry-market-series" queryId="industry_metrics" title={seriesTitle}
          {...scoped} rows={plottedRows} sourceRows={observations} height={300}
          spec={{ type: "bar", x: "Observation year", y: valueField, startAtZero: true, stackable: false, valueDecimals: 1,
            showXAxisLabel: false, showYAxisLabel: false, colors: { [valueField]: /audio/i.test(latest?.metric ?? "") ? "var(--chart-2)" : "var(--chart-1)" } }}>
          {latest ? <div className="atlas-profile-context" data-reviewed-rows><dl>
            <div><dt>Country and revenue measure</dt><dd>{latest.country} · {latest.metric}</dd></div>
            <div><dt>Unit</dt><dd>{latest.unit}</dd></div>
            <div><dt>Source population / scope</dt><dd>{latest.scope}</dd></div>
            <div><dt>Latest available observation</dt><dd>{latest.year}; published {latest.publication_date ?? "date not supplied"}</dd></div>
            <div><dt>Source checked</dt><dd>{fmtChecked(sourceCheck?.last_checked_at)} (UTC)</dd></div>
          </dl></div> : <Note>Choose a country and revenue measure to view its published figures.</Note>}
          {hasVintageBreak && <Note tone="caution">Original release vintages are shown. Later releases revise earlier amounts, so these bars are not a harmonized growth series. Do not interpret differences between bars as annual growth or decline, or calculate a continuous growth rate.</Note>}
          <Note tone="caution">Each chart keeps one source definition and currency. Publisher receipts, retail turnover and operating revenue cover different parts of the market. They cannot form a country ranking. Only verified observation years are shown. {latest?.notes}</Note>
        </EvidenceChart> : <DataComponent variant="card" id="industry-market-series" queryId="sources" title="Sales and revenue by year" kind="custom" displayRows={[]} sourceRows={[]}><Note>Reviewed industry statistics are being prepared.</Note></DataComponent>}
      </Block>
      <Block id="industry-company-register" title="Companies and public evidence" span={12} kind="table">
        <DataComponent variant="card" id="industry-company-register" queryId={queries.companies ? "companies" : "sources"}
          title="Companies and public evidence" kind="table" displayRows={companies} sourceRows={companies}>
          {companies.length ? <DataTable rows={companies} columns={companyColumns} label="Book industry company register with formats, scope and public data" rowKey="company_id" /> : <Note>The reviewed company register is being prepared.</Note>}
          <Note>The register covers reviewed public sources and is not an exhaustive list of every book company. Company-wide subscribers, revenue or users are not assumed to be audiobook-only figures.</Note>
        </DataComponent>
      </Block>
    </SortableRegion>
  </>;
}

function Audiobooks() {
  const { queries, reviewedRows } = useDataApp();
  const audioQueryId = queries.audiobook_evidence ? "audiobook_evidence" : "format_profiles";
  const historyQueryId = queries.audiobook_history ? "audiobook_history" : audioQueryId;
  const originalHistory = (queries[historyQueryId]?.rows ?? []).filter(row => (!row.format_label || row.format_label === "Audiobook") && row.year >= 2022);
  const initialHistoryCountry = originalHistory.some(row => row.country === "Sweden") ? "Sweden" : originalHistory[0]?.country ?? "Sweden";
  const initialHistoryGroup = originalHistory.find(row => row.country === initialHistoryCountry)?.comparison_group ?? "all";
  const scope = useSectionFilters([
    { id: "country", label: "Country", field: "country", defaultValue: "Sweden", queryIds: [audioQueryId] },
  ], {}, { rowId: "atlas:audio:profile", componentIds: ["audiobook-country-profile"], label: "Audiobook evidence country" });
  const scoped = scope.componentProps(audioQueryId, ["country", "year", "format_label"]);
  const profile = scope.values.country === "all" ? [] : scoped.sourceRows.filter(row => !row.format_label || row.format_label === "Audiobook");
  const observation = profile.length === 1 ? profile[0] : null;
  const historyScope = useSectionFilters([
    { id: "country", label: "Country", field: "country", defaultValue: initialHistoryCountry, queryIds: [historyQueryId] },
    { id: "comparison_group", label: "Measure", field: "comparison_group", defaultValue: initialHistoryGroup, queryIds: [historyQueryId] },
  ], {}, { rowId: "atlas:audio:history", componentIds: ["audiobook-history"], label: "Audiobook history filters" });
  const historyDefinitions = [...new Set(originalHistory.filter(row => row.country === historyScope.values.country).map(row => row.comparison_group).filter(Boolean))];
  useEffect(() => {
    if (historyScope.values.country !== "all" && historyScope.values.comparison_group !== "all" && historyDefinitions.length
      && !historyDefinitions.includes(historyScope.values.comparison_group)) historyScope.setFilter("comparison_group", historyDefinitions[0]);
  }, [historyScope.values.country, historyScope.values.comparison_group, JSON.stringify(historyDefinitions)]);
  const historyProps = historyScope.componentProps(historyQueryId, ["year", "country", "comparison_group"]);
  const historyRows = historyScope.values.country === "all" || historyScope.values.comparison_group === "all" ? []
    : historyProps.sourceRows.filter(row => (!row.format_label || row.format_label === "Audiobook") && row.year >= 2022).sort((a, b) => a.year - b.year);
  const latestHistory = historyRows.at(-1);
  const freshness = queries.data_freshness ? reviewedRows("data_freshness", ["source_id"]) : [];
  const checkFor = sourceId => freshness.find(row => row.source_id === sourceId);
  const profileCheck = checkFor(observation?.source_id);
  const historyCheck = checkFor(latestHistory?.source_id);
  const checkedYears = freshness.map(row => Number(String(row.last_checked_at ?? "").slice(0, 4))).filter(year => year >= 2022);
  const checkedYear = Math.max(2026, ...checkedYears);
  const observedYears = new Set(historyRows.map(row => row.year));
  const missingYears = Array.from({ length: checkedYear - 2022 + 1 }, (_, index) => 2022 + index).filter(year => !observedYears.has(year));
  const historyControls = <Filters {...historyScope.filterProps} filters={[]}>
    <Dropdown label="Country" showLabel value={historyScope.values.country} choices={[...new Set(originalHistory.map(row => row.country))]}
      allLabel="Choose one country" onChange={value => historyScope.setFilter("country", value)} />
    <Dropdown label="Measure" showLabel value={historyScope.values.comparison_group} choices={historyDefinitions}
      allLabel="Choose one measure" onChange={value => historyScope.setFilter("comparison_group", value)} />
  </Filters>;
  const genreQueryId = queries.genre_history ? "genre_history" : "genre_profiles";
  const originalAudioGenres = (queries[genreQueryId]?.rows ?? []).filter(row => row.country_iso3 === "CAN" && row.format_label === "Audiobook");
  const genreYears = surveyYearChoices(originalAudioGenres);
  const genreScope = useSectionFilters([
    { id: "genre_scope", label: "Genre scope", field: "genre_scope", defaultValue: "Book fiction genres", queryIds: [genreQueryId] },
    { id: "year", label: "Survey year", field: "year", defaultValue: genreYears[0] ?? "all", queryIds: [genreQueryId] },
  ], {}, { rowId: "atlas:audio:genres", componentIds: ["audio-canada-genres"], label: "Canadian audiobook genre scope" });
  const genreProps = genreScope.componentProps(genreQueryId, ["year", "genre", "format_label"]);
  const audioGenres = genreScope.values.genre_scope === "all" || genreScope.values.year === "all" ? []
    : genreProps.sourceRows.filter(row => row.country_iso3 === "CAN" && row.format_label === "Audiobook" && String(row.year) === String(genreScope.values.year));
  const availableAudioGenres = audioGenres.filter(row => Number.isFinite(row.participation));
  const missingAudioGenres = audioGenres.filter(row => !Number.isFinite(row.participation)).map(row => row.genre);
  const genreControls = <Filters {...genreScope.filterProps} filters={[]}><Dropdown label="Genre scope" showLabel
    value={genreScope.values.genre_scope} choices={["Book fiction genres", "Book non-fiction genres"]}
    allLabel="Choose one scope" onChange={value => genreScope.setFilter("genre_scope", value)} />
    <Dropdown label="Survey year" showLabel value={genreScope.values.year} choices={genreYears}
      allLabel="Choose one year" onChange={value => genreScope.setFilter("year", value)} /></Filters>;
  const hasComparableStudy = Boolean(queries.storytel_audio_2026);
  const studyScope = useSectionFilters([
    { id: "country", label: "Survey country", field: "country", defaultValue: "Sweden", queryIds: ["storytel_audio_2026"] },
  ], {}, { rowId: "atlas:audio:study", componentIds: ["audio-study-genres", "audio-study-moments"], label: "Comparable listening survey country" });
  const studyProps = studyScope.componentProps("storytel_audio_2026", ["country", "year", "record_type", "item"]);
  const selectedStudy = studyScope.values.country === "all" ? [] : studyProps.sourceRows;
  const studyGenres = selectedStudy.filter(row => row.record_type === "genre");
  const studyMoments = selectedStudy.filter(row => row.record_type === "moment");
  const allStudy = hasComparableStudy ? reviewedRows("storytel_audio_2026", ["country", "year", "record_type", "item"]) : [];
  const crimeRows = allStudy.filter(row => row.record_type === "genre" && row.item === "Crime/Thriller");
  const preferenceRows = rows => rows.map(row => ({ ...row, [PREFERENCE]: row.participation }));
  const preferenceBar = (x, color) => ({ type: "horizontalBar", x, y: PREFERENCE, valueDecimals: 0,
    startAtZero: true, stackable: false, showXAxisLabel: false, showYAxisLabel: false, sortOrder: "descending", colors: { [PREFERENCE]: color } });
  return <>
    <Note>Audiobook participation, genres and listening occasions support research across the book industry. National surveys and listener studies retain their own populations and observation periods.</Note>
    <SortableRegion id="atlas:audio:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:audio:profile", items: ["audiobook-country-profile"], header: <SectionHeader id="audio-profile-heading" title="Audiobook demand evidence" filters={<Filters {...scope.filterProps} />} /> },
      { id: "atlas:audio:history", items: ["audiobook-history"], header: <SectionHeader id="audio-history-heading" title="Audiobook history from 2022 onwards" filters={historyControls} /> },
      ...(hasComparableStudy ? [
        { id: "atlas:audio:study", items: ["audio-study-genres", "audio-study-moments"], header: <SectionHeader id="audio-study-heading" title="2026 audiobook listener survey" filters={<Filters {...studyScope.filterProps} />} /> },
        { id: "atlas:audio:study-comparison", items: ["audio-crime-comparison"], header: <SectionHeader id="audio-study-comparison-heading" title="Sponsored study: same-question comparison across five markets" /> },
      ] : []),
      { id: "atlas:audio:genres", items: ["audio-canada-genres"], header: <SectionHeader id="audio-genres-heading" title={`Canada: audiobook genres${genreScope.values.year !== "all" ? `, ${genreScope.values.year}` : ""}`} filters={genreControls} /> },
      { id: "atlas:audio:freshness", items: ["audio-source-freshness"], header: <SectionHeader id="audio-freshness-heading" title="Source checks and update methods" /> },
    ]}>
      <Block id="audiobook-country-profile" title="Audiobook participation within one survey" span={12} kind="custom">
        <DataComponent variant="card" id="audiobook-country-profile" queryId={audioQueryId} title="Audiobook participation within one survey" kind="custom"
          {...scoped} displayRows={profile} sourceRows={profile} description="A single audiobook observation retains the source population, denominator and period. No pooled rate or country ranking is calculated.">
          {observation ? <div className="atlas-audio-profile" data-reviewed-rows>
            <div className="atlas-audio-measure"><strong>{fmt(observation.participation)}</strong><span>{observation.country}, {observation.year}</span><small>Audiobook participation · {observation.period}</small></div>
            <div className="atlas-profile-context"><dl>
              <div><dt>Denominator</dt><dd>{observation.denominator}</dd></div>
              <div><dt>Population</dt><dd>{observation.population}</dd></div>
              <div><dt>Measurement period</dt><dd>{observation.period}</dd></div>
              <div><dt>Original source</dt><dd><SourceLink url={observation.source_url}>{observation.source_id}</SourceLink></dd></div>
            </dl></div>
          </div> : <Note>Select one country to inspect its exact listening measure.</Note>}
          {observation && <Note>Latest observation in this profile: {observation.year}. Source checked: {fmtChecked(profileCheck?.last_checked_at)} (UTC).</Note>}
          <Note tone="caution">{observation?.notes ? `${observation.notes} ` : ""}Public listening profiles use population participation, reader subsets or listening frequency. Their percentages cannot be ranked together as market demand.</Note>
        </DataComponent>
      </Block>
      <Block id="audiobook-history" title="Observed audiobook participation by survey year" span={12}>
        <Plot id="audiobook-history" queryId={historyQueryId} title="Observed audiobook participation by survey year"
          rows={historyRows.map(row => ({ ...row, "Survey year": String(row.year) }))} spec={{ ...bar("Survey year"), type: "bar", colors: { [RATE]: "var(--chart-2)" } }}
          height={260} {...historyProps} sourceRows={historyRows}>
          {latestHistory ? <div className="atlas-profile-context" data-reviewed-rows><dl>
            <div><dt>Selected measure</dt><dd>{latestHistory.country} · {latestHistory.comparison_group}</dd></div>
            <div><dt>Denominator and period</dt><dd>{latestHistory.denominator} · {latestHistory.period}</dd></div>
            <div><dt>Latest observation</dt><dd>{latestHistory.year}</dd></div>
            <div><dt>Source checked</dt><dd>{fmtChecked(historyCheck?.last_checked_at)} (UTC)</dd></div>
          </dl></div> : <Note>Select one country and one measure to inspect available observations.</Note>}
          <Note tone="caution">Requested window: 2022–{checkedYear}. Only verified observations are plotted, with survey years spaced equally. {historyRows.length && missingYears.length ? `No verified observation for ${missingYears.join(", ")}. ` : ""}No annual values are generated to fill gaps. {latestHistory?.notes}</Note>
        </Plot>
      </Block>
      <Block id="audio-canada-genres" title="Audiobook genres within one reader panel" span={12}>
        <Plot id="audio-canada-genres" queryId={genreQueryId} title="Audiobook genres within one reader panel"
          rows={availableAudioGenres} spec={bar("genre", { sortOrder: "descending", colors: { [RATE]: "var(--chart-2)" } })}
          height={Math.max(260, availableAudioGenres.length * 29)} {...genreProps} sourceRows={audioGenres}>
          <Note tone="caution">Canada{genreScope.values.year !== "all" ? `, ${genreScope.values.year}` : ""}; English-speaking adult internet panel, unweighted. {audioGenres[0]?.denominator ?? "Select one book genre scope and one year."} Exact eligible audiobook genre subgroup sample sizes are unpublished; the overall reader panel size is not the genre denominator. Readers could choose up to three genres, so percentages cannot be added. {missingAudioGenres.length ? `Unavailable genre values: ${missingAudioGenres.join(", ")}. ` : ""}These genre selections do not establish local catalogue demand or commercial return.</Note>
        </Plot>
      </Block>
      {hasComparableStudy && <Block id="audio-study-genres" title="Audiobook genre choices" span={6}>
        <EvidenceChart variant="card" id="audio-study-genres" queryId="storytel_audio_2026" title="Audiobook genre choices"
          {...studyProps} rows={preferenceRows(studyGenres)} sourceRows={studyGenres} spec={preferenceBar("item", "var(--chart-2)")} height={290}>
          <Note tone="caution">{studyGenres[0]?.year ?? "2026"} online panel, age 18–79. Audiobook listener eligibility and subgroup sample sizes are unpublished. Only the country’s top five genres are reported; unlisted choices are unreported, never zero.</Note>
        </EvidenceChart>
      </Block>}
      {hasComparableStudy && <Block id="audio-study-moments" title="Audiobook listening moments" span={6}>
        <EvidenceChart variant="card" id="audio-study-moments" queryId="storytel_audio_2026" title="Audiobook listening moments"
          {...studyProps} rows={preferenceRows(studyMoments)} sourceRows={studyMoments} spec={preferenceBar("item", "var(--chart-3)")} height={290}>
          <Note>Usual listening, with no explicit recall period. These responses describe surveyed listeners, not national audiobook participation or Storytel customers. Multiple responses are implied; the exact response instruction is unpublished.</Note>
        </EvidenceChart>
      </Block>}
      {hasComparableStudy && <Block id="audio-crime-comparison" title="Crime/Thriller choices among surveyed listeners" span={12}>
        <EvidenceChart variant="card" id="audio-crime-comparison" queryId="storytel_audio_2026" title="Crime/Thriller choices among surveyed listeners"
          rows={preferenceRows(crimeRows)} sourceRows={crimeRows} spec={preferenceBar("country", "var(--chart-2)")} height={275}>
          <Note tone="caution">Same question in the April 2026 survey, commissioned by Storytel and conducted by Trackit Insight. Total online panel: 5,077 respondents, about 1,000 per market; listener subgroup bases are unpublished. Crime/Thriller appears in all five published genre lists. This comparison informs content research and does not rank national listening demand or commercial opportunity.</Note>
        </EvidenceChart>
      </Block>}
      <Block id="audio-source-freshness" title="Source freshness and refresh readiness" span={12} kind="table">
        <DataComponent variant="card" id="audio-source-freshness" queryId={queries.data_freshness ? "data_freshness" : "sources"}
          title="Source freshness and refresh readiness" kind="table" displayRows={freshness} sourceRows={freshness}>
          {freshness.length ? <DataTable rows={freshness} rowKey="source_id" searchable={false} label="Source observation years, checks and update methods" columns={[
            { field: "source_name", label: "Source", presentation: "identity", secondaryField: "source_id" },
            { field: "latest_observation_year", label: "Latest observation" },
            { field: "last_checked_at", label: "Last checked (UTC)", renderCell: fmtChecked },
            { field: "status", label: "Status", presentation: "status" },
            { field: "update_method", label: "Update method" },
            { field: "notes", label: "Coverage and limits" },
          ]} /> : <Note>Source freshness records are pending. An automatic refresh must keep manual PDF checks and source release delays visible.</Note>}
          <Note>A new source check does not create a new survey observation. Source years and refresh status remain separate.</Note>
        </DataComponent>
      </Block>
    </SortableRegion>
  </>;
}

function Reading() {
  const { reviewedRows } = useDataApp();
  const rankingScope = useSectionFilters([
    { id: "scope", label: "Countries", field: "scope", defaultValue: "all", queryIds: ["europe"] },
  ], {}, { id: "atlas-reading-countries", label: "Country comparison filters" });
  const profileScope = useSectionFilters([
    { id: "country", label: "Country", field: "country", defaultValue: "Sweden", queryIds: ["demographics"] },
  ], {}, { rowId: "atlas:reading:profile", componentIds: ["age-profile", "sex-profile", "education-profile"], label: "Country profile filters" });
  const countrySource = rankingScope.componentProps("europe", ["country"]);
  const countries = countrySource.sourceRows;
  const available = countries.filter(row => Number.isFinite(row.participation));
  const sortedValues = available.map(row => row.participation).sort((a, b) => a - b);
  const middle = Math.floor(sortedValues.length / 2);
  const median = sortedValues.length ? sortedValues.length % 2 ? sortedValues[middle] : (sortedValues[middle - 1] + sortedValues[middle]) / 2 : null;
  const benchmark = reviewedRows("eu_benchmark");
  const includedCountries = new Set(countries.map(row => row.country_iso3));
  const gapRows = reviewedRows("gender_gaps", ["country"]).filter(row => includedCountries.has(row.country_iso3));
  const plottedGapRows = gapRows.filter(row => Number.isFinite(row.gap_pp)).map(row => ({ ...row, "Women minus men (pp)": row.gap_pp }));
  const profileProps = profileScope.componentProps("demographics", ["age", "sex", "isced11"]);
  const profile = profileScope.values.country === "all" ? [] : profileProps.sourceRows;
  const ages = profile.filter(row => row.sex === "T" && row.isced11 === "TOTAL" && row.age !== "Y_GE16")
    .map(row => ({ ...row, age_group: { "Y16-29": "16–29", "Y30-54": "30–54", "Y55-64": "55–64", "Y_GE65": "65+" }[row.age] ?? row.age_label }));
  const sex = profile.filter(row => row.age === "Y_GE16" && row.isced11 === "TOTAL" && row.sex !== "T");
  const education = profile.filter(row => row.sex === "T" && row.age === "Y_GE16" && row.isced11 !== "TOTAL")
    .map(row => ({ ...row, education_group: { "ED0-2": "Lower secondary or less", "ED3_4": "Upper secondary / post-secondary", "ED5-8": "Tertiary" }[row.isced11] ?? row.education_label }));
  const countryProfileContext = profileScope.values.country === "all" ? "Select one country for its demographic profile. Country rates cannot be pooled without population weights."
    : `${profileScope.values.country} · age 16+ · 2022 · past 12 months`;
  return <>
    <Note>At least one book in the past 12 months, age 16+. Eurostat includes print, ebooks and audiobooks in this measure. These are 2022 observations.</Note>
    <Filters {...rankingScope.filterProps} />
    <SortableRegion id="atlas:reading:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:reading:metrics", kind: "metrics", items: ["eu-participation", "country-median", "available-countries"] },
      { id: "atlas:reading:comparisons", items: ["country-participation", "country-gender-gap"], header: <SectionHeader id="reading-comparison-heading" title="European country comparisons" /> },
      { id: "atlas:reading:profile", items: ["age-profile", "sex-profile", "education-profile"], header: <SectionHeader id="reading-profile-heading" title="Country demographic profile" filters={<Filters {...profileScope.filterProps} />} /> },
    ]}>
      <Block id="eu-participation" title="EU official participation" span={4} kind="metric">
        <MetricCard id="eu-participation" queryId="eu_benchmark" title="EU official participation" value={fmt(benchmark[0]?.participation)}
          displayRows={benchmark} sourceRows={benchmark} description="Official EU27 aggregate, estimated, age 16+, 2022. This is not an average of the displayed countries." />
      </Block>
      <Block id="country-median" title="Unweighted country median" span={4} kind="metric">
        <MetricCard id="country-median" queryId="europe" title="Unweighted country median" value={fmt(median)}
          displayRows={[{ country_median: median, country_estimates: available.length }]} sourceRows={countries} scopeFilters={countrySource.scopeFilters}
          description="Median of available country participation rates in the selected scope. Every country has equal weight; this does not estimate the share of all European people." />
      </Block>
      <Block id="available-countries" title="Country estimates available" span={4} kind="metric">
        <MetricCard id="available-countries" queryId="europe" title="Country estimates available" value={`${available.length} / ${countries.length}`}
          displayRows={[{ available_estimates: available.length, reviewed_countries: countries.length }]} sourceRows={countries} scopeFilters={countrySource.scopeFilters}
          description="Available participation estimates divided by the reviewed country roster in the selected scope. Missing and unreliable observations are retained in source records." />
      </Block>
      <Block id="country-participation" title="Book participation by country" span={7}>
        <Plot id="country-participation" queryId="europe" title="Book participation by country" rows={available}
          spec={bar("country", { sortOrder: "descending", colors: { [RATE]: "var(--chart-1)" } })} height={Math.max(340, available.length * 27)}
          {...countrySource} sourceRows={countries}>
          <Note>Germany has no usable result in the reviewed extract. Estimated values and source flags remain in the source records. Percentages describe participation, not books sold.</Note>
        </Plot>
      </Block>
      <Block id="country-gender-gap" title="Gender participation gap" span={5}>
        <EvidenceChart variant="card" id="country-gender-gap" queryId="gender_gaps" title="Gender participation gap"
          rows={plottedGapRows} sourceRows={gapRows} scopeFilters={countrySource.scopeFilters} sectionFilters={countrySource.sectionFilters}
          spec={{ type: "horizontalBar", x: "country", y: "Women minus men (pp)", sortOrder: "descending", startAtZero: true,
            stackable: false, valueDecimals: 1, colors: { "Women minus men (pp)": "var(--chart-2)" }, showXAxisLabel: false, showYAxisLabel: false }}
          height={Math.max(340, available.length * 27)}>
          <Note>Women’s rate minus men’s rate, in percentage points. These descriptive differences do not identify their causes.</Note>
        </EvidenceChart>
      </Block>
      <Block id="age-profile" title="Participation by age" span={4}>
        <Plot id="age-profile" queryId="demographics" title="Participation by age" rows={ages} spec={bar("age_group")} height={250}
          {...profileProps} sourceRows={ages} description={countryProfileContext}>
          <Note>{countryProfileContext}</Note>
        </Plot>
      </Block>
      <Block id="sex-profile" title="Participation by sex" span={4}>
        <Plot id="sex-profile" queryId="demographics" title="Participation by sex" rows={sex}
          spec={bar("sex_label", { colors: { [RATE]: "var(--chart-2)" } })} height={250}
          {...profileProps} sourceRows={sex} description={countryProfileContext} />
      </Block>
      <Block id="education-profile" title="Participation by education" span={4}>
        <Plot id="education-profile" queryId="demographics" title="Participation by education" rows={education}
          spec={bar("education_group", { colors: { [RATE]: "var(--chart-3)" } })} height={250}
          {...profileProps} sourceRows={education} description={countryProfileContext}>
          <Note>ISCED 2011 education groups. Unavailable subgroup observations are gaps, never zero.</Note>
        </Plot>
      </Block>
    </SortableRegion>
  </>;
}

function Formats() {
  const { reviewedRows, queries } = useDataApp();
  const historyQueryId = queries.format_history ? "format_history" : "format_profiles";
  const originalHistory = (queries[historyQueryId]?.rows ?? []).filter(row => ["SWE", "NOR"].includes(row.country_iso3) && row.year >= 2022);
  const historyScope = useSectionFilters([
    { id: "country", label: "Country", field: "country", defaultValue: "Sweden", queryIds: [historyQueryId] },
  ], {}, { rowId: "atlas:formats:history", componentIds: ["national-format-history"], label: "National format history country" });
  const historyProps = historyScope.componentProps(historyQueryId, ["country", "year", "format_label"]);
  const historyRows = historyScope.values.country === "all" ? [] : historyProps.sourceRows.filter(row => ["SWE", "NOR"].includes(row.country_iso3) && row.year >= 2022).sort((a, b) => a.year - b.year);
  const historyWaves = [...new Set(historyRows.map(row => row.year))].map(year => ({
    year, "Survey year": String(year),
    ...Object.fromEntries(["Print", "Ebook", "Audiobook"].map(format => [
      `${format} (%)`, historyRows.find(row => row.year === year && row.format_label === format)?.participation ?? null,
    ])),
  }));
  const latestHistory = historyRows.at(-1);
  const historyPopulation = [...new Set(historyRows.map(row => row.population).filter(Boolean))];
  const historyFreshness = queries.data_freshness?.rows ?? [];
  const historyCheck = historyFreshness.find(row => row.source_id === latestHistory?.source_id);
  const checkedYears = historyFreshness.map(row => Number(String(row.last_checked_at ?? "").slice(0, 4))).filter(year => year >= 2022);
  const requestedEndYear = Math.max(2026, ...checkedYears);
  const observedYears = new Set(historyRows.map(row => row.year));
  const missingYears = Array.from({ length: requestedEndYear - 2022 + 1 }, (_, index) => 2022 + index).filter(year => !observedYears.has(year));
  const historyControls = <Filters {...historyScope.filterProps} filters={[]}><Dropdown label="Country" showLabel
    value={historyScope.values.country} choices={[...new Set(originalHistory.map(row => row.country))]}
    allLabel="Choose one country" onChange={value => historyScope.setFilter("country", value)} /></Filters>;
  const formatHistoryChart = { type: "bar", x: "Survey year", y: "Print (%)", fields: ["Print (%)", "Ebook (%)", "Audiobook (%)"],
    startAtZero: true, stackable: false, valueDecimals: 0, showXAxisLabel: false, showYAxisLabel: false,
    colors: Object.fromEntries(Object.entries(formatColors).map(([format, color]) => [`${format} (%)`, color])),
    legend: { labels: { "Print (%)": "Print", "Ebook (%)": "Ebook", "Audiobook (%)": "Audiobook" } } };
  const allUS = reviewedRows("us_formats", ["year", "format_label"]);
  const historical = allUS.filter(row => row.year <= 2021);
  const recent = allUS.filter(row => row.year === 2025);
  const historicalWaves = [...new Set(historical.map(row => row.year))].sort((a, b) => a - b).map(year => ({
    year,
    "Survey year (equally spaced waves)": String(year),
    ...Object.fromEntries(["Print", "Ebook", "Audiobook"].map(format => [
      `${format} (%)`, historical.find(row => row.year === year && row.format_label === format)?.participation ?? null,
    ])),
  }));
  const profileQueryId = queries.format_history ? "format_history" : "format_profiles";
  const originalProfiles = queries[profileQueryId]?.rows ?? [];
  const initialProfileYear = surveyYearChoices(originalProfiles.filter(row => row.country === "Canada"))[0] ?? "all";
  const scope = useSectionFilters([
    { id: "country", field: "country", label: "Country", defaultValue: "Canada", queryIds: [profileQueryId] },
    { id: "year", field: "year", label: "Survey year", defaultValue: initialProfileYear, queryIds: [profileQueryId] },
  ], {}, { rowId: "atlas:formats:profile", componentIds: ["national-format-profile"], label: "National format profile filters" });
  const profileYears = surveyYearChoices(originalProfiles.filter(row => row.country === scope.values.country));
  useEffect(() => {
    if (scope.values.country !== "all" && scope.values.year !== "all" && profileYears.length
      && !profileYears.includes(String(scope.values.year))) scope.setFilter("year", profileYears[0]);
  }, [scope.values.country, scope.values.year, JSON.stringify(profileYears)]);
  const scoped = scope.componentProps(profileQueryId, ["country", "year", "format_label"]);
  const profile = scope.values.country === "all" || scope.values.year === "all" ? []
    : scoped.sourceRows.filter(row => row.country === scope.values.country && String(row.year) === String(scope.values.year));
  const metadata = profile[0];
  const profileControls = <Filters {...scope.filterProps} filters={[]}>
    <Dropdown label="Country" showLabel value={scope.values.country} choices={[...new Set(originalProfiles.map(row => row.country))]}
      allLabel="Choose one country" onChange={value => scope.setFilter("country", value)} />
    <Dropdown label="Survey year" showLabel value={scope.values.year} choices={profileYears}
      allLabel="Choose one year" onChange={value => scope.setFilter("year", value)} />
  </Filters>;
  const trend = { type: "bar", x: "Survey year (equally spaced waves)", y: "Print (%)",
    fields: ["Print (%)", "Ebook (%)", "Audiobook (%)"], stackable: false,
    colors: Object.fromEntries(Object.entries(formatColors).map(([format, color]) => [`${format} (%)`, color])),
    legend: { labels: { "Print (%)": "Print", "Ebook (%)": "Ebook", "Audiobook (%)": "Audiobook" } },
    showXAxisLabel: true, showYAxisLabel: false, valueDecimals: 0, startAtZero: true };
  return <>
    <Note>Reading and listening can overlap. Annual adult participation, reader subsets and daily reach each answer a different question.</Note>
    <SortableRegion id="atlas:formats:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:formats:history", items: ["national-format-history"], header: <SectionHeader id="formats-history-heading" title="Nordic print, ebook and audiobook history" filters={historyControls} /> },
      { id: "atlas:formats:us", items: ["us-format-history", "us-format-2025"], header: <SectionHeader id="formats-us-heading" title="United States: print, ebooks and audio" /> },
      { id: "atlas:formats:profile", items: ["national-format-profile"], header: <SectionHeader id="formats-profile-heading" title="National format profiles" filters={profileControls} /> },
    ]}>
      <Block id="national-format-history" title="Observed daily format reach by survey year" span={12}>
        <EvidenceChart variant="card" id="national-format-history" queryId={historyQueryId} title="Observed daily format reach by survey year"
          {...historyProps} rows={historyWaves} sourceRows={historyRows} spec={formatHistoryChart} height={320}>
          {latestHistory ? <div className="atlas-profile-context" data-reviewed-rows><dl>
            <div><dt>Country</dt><dd>{latestHistory.country}</dd></div>
            <div><dt>Measurement period</dt><dd>{latestHistory.period}</dd></div>
            <div><dt>Population across observed waves</dt><dd>{historyPopulation.join("; ")}</dd></div>
            <div><dt>Latest observation / source check</dt><dd>{latestHistory.year} / {fmtChecked(historyCheck?.last_checked_at)} (UTC)</dd></div>
          </dl></div> : <Note>Select Sweden or Norway to inspect its published format history.</Note>}
          <Note tone="caution">Requested window: 2022–{requestedEndYear}. Only verified survey waves are shown. {historyRows.length && missingYears.length ? `No verified observation for ${missingYears.join(", ")}. ` : ""}No annual values are generated to fill gaps. Print, ebook and audiobook reach overlap, so their percentages cannot be added. Keep each country’s age scope explicit. {latestHistory?.notes}</Note>
        </EvidenceChart>
      </Block>
      <Block id="us-format-history" title="US format participation, 2011–2021" span={8}>
        <EvidenceChart variant="card" id="us-format-history" queryId="us_formats" title="US format participation, 2011–2021"
          rows={historicalWaves} sourceRows={historical} spec={trend} height={360}>
          <Note>Observed survey measurements; no estimates between surveys. Survey waves are spaced equally. US adults age 18+; at least part of a book in the past 12 months. Phone surveys through 2021.</Note>
        </EvidenceChart>
      </Block>
      <Block id="us-format-2025" title="US format participation, 2025" span={4}>
        <Plot id="us-format-2025" queryId="us_formats" title="US format participation, 2025" rows={recent}
          spec={bar("format_label")} height={360}>
          <Note tone="caution">2025 used web and phone interviews. The separate chart preserves this survey mode break; changes from 2021 require care.</Note>
        </Plot>
      </Block>
      <Block id="national-format-profile" title="Format participation within one survey" span={12}>
        {queries[profileQueryId] ? <Plot id="national-format-profile" queryId={profileQueryId} title="Format participation within one survey"
          rows={profile} spec={bar("format_label")} height={250} {...scoped} sourceRows={profile}>
          {metadata ? <div className="atlas-profile-context" data-reviewed-rows>
            <dl><div><dt>Country and year</dt><dd>{metadata.country}, {metadata.year}</dd></div>
              <div><dt>Measurement period</dt><dd>{metadata.period}</dd></div>
              <div><dt>Denominator</dt><dd>{metadata.denominator}</dd></div>
              <div><dt>Population</dt><dd>{metadata.population}</dd></div></dl>
            <Note tone="caution">{metadata.notes} These national figures are not a cross-country ranking.</Note>
          </div> : <Note>Select one country and one survey year. Its period and population will appear alongside the chart.</Note>}
        </Plot> : <DataComponent variant="card" id="national-format-profile" queryId="sources" title="National format profiles" kind="custom" displayRows={[]} sourceRows={[]}><Note>National format extracts are pending verification.</Note></DataComponent>}
      </Block>
    </SortableRegion>
  </>;
}

function Genres() {
  const { reviewedRows, queries } = useDataApp();
  const historyQueryId = queries.genre_history ? "genre_history" : "genre_profiles";
  const listenerQueryId = "storytel_audio_2026";
  const historyGenres = (queries[historyQueryId]?.rows ?? []).filter(row => row.year >= 2022);
  const listenerOriginal = (queries[listenerQueryId]?.rows ?? []).filter(row => row.year >= 2022 && row.record_type === "genre");
  const genreQueryIds = [historyQueryId, listenerQueryId].filter(queryId => queries[queryId]);
  const allGenres = [...historyGenres, ...listenerOriginal];
  const queryBySource = new Map([
    ...historyGenres.map(row => [row.source_id, historyQueryId]),
    ...listenerOriginal.map(row => [row.source_id, listenerQueryId]),
  ]);
  const choicesFor = (rows, field) => [...new Set(rows.map(row => row[field]).filter(value => value != null && value !== ""))].map(String).sort();
  const countries = choicesFor(allGenres, "country");
  const initialCountry = countries.includes("France") ? "France" : countries[0] ?? "all";
  const initialCountryRows = allGenres.filter(row => row.country === initialCountry);
  const initialSource = choicesFor(initialCountryRows, "source_id")[0] ?? "all";
  const initialSourceRows = initialCountryRows.filter(row => row.source_id === initialSource);
  const initialYear = surveyYearChoices(initialSourceRows)[0] ?? "all";
  const initialYearRows = initialSourceRows.filter(row => String(row.year) === initialYear);
  const initialQuestion = choicesFor(initialYearRows, "genre_scope")[0] ?? "all";
  const initialQuestionRows = initialYearRows.filter(row => row.genre_scope === initialQuestion);
  const initialFormatChoices = choicesFor(initialQuestionRows, "format_label");
  const initialFormat = initialFormatChoices.includes("Audiobook") ? "Audiobook" : initialFormatChoices[0] ?? "all";
  const sourceLabels = Object.fromEntries((queries.sources?.rows ?? []).map(row => [row.source_id, row.title ?? row.provider ?? row.source_id]));
  const explorer = useSectionFilters([
    { id: "country", label: "Country", field: "country", defaultValue: initialCountry, queryIds: genreQueryIds },
    { id: "source_id", label: "Survey source", field: "source_id", defaultValue: initialSource, queryIds: genreQueryIds, choiceLabels: sourceLabels },
    { id: "year", label: "Observation year", field: "year", defaultValue: initialYear, queryIds: genreQueryIds },
    { id: "genre_scope", label: "Genre question", field: "genre_scope", defaultValue: initialQuestion, queryIds: genreQueryIds },
    { id: "format_label", label: "Format", field: "format_label", defaultValue: initialFormat, queryIds: genreQueryIds },
  ], {}, { rowId: "atlas:genres:explorer", componentIds: ["genre-country-explorer"], label: "Source-specific genre study filters" });
  const countrySources = allGenres.filter(row => row.country === explorer.values.country);
  const sourceChoices = choicesFor(countrySources, "source_id");
  const sourceRows = countrySources.filter(row => row.source_id === explorer.values.source_id);
  const yearChoices = surveyYearChoices(sourceRows);
  const yearRows = sourceRows.filter(row => String(row.year) === String(explorer.values.year));
  const questionChoices = choicesFor(yearRows, "genre_scope");
  const questionRows = yearRows.filter(row => row.genre_scope === explorer.values.genre_scope);
  const formatChoices = choicesFor(questionRows, "format_label");
  useEffect(() => {
    const dependentChoices = [
      ["source_id", sourceChoices], ["year", yearChoices],
      ["genre_scope", questionChoices], ["format_label", formatChoices],
    ];
    for (const [field, available] of dependentChoices) {
      if (explorer.values[field] !== "all" && available.length && !available.includes(String(explorer.values[field]))) {
        explorer.setFilter(field, field === "format_label" && available.includes("Audiobook") ? "Audiobook" : available[0]);
        return;
      }
    }
  }, [explorer.values.country, explorer.values.source_id, explorer.values.year, explorer.values.genre_scope, explorer.values.format_label,
    JSON.stringify(sourceChoices), JSON.stringify(yearChoices), JSON.stringify(questionChoices), JSON.stringify(formatChoices)]);
  const explorerQueryId = queryBySource.get(explorer.values.source_id) ?? historyQueryId;
  const selectedExplorerProps = explorer.componentProps(explorerQueryId, ["country", "source_id", "year", "genre_scope", "format_label", "genre", "record_type"]);
  const explorerProps = explorerQueryId === listenerQueryId ? {
    ...selectedExplorerProps,
    scopeFilters: [...selectedExplorerProps.scopeFilters, { field: "record_type", label: "Response type", value: "genre" }],
  } : selectedExplorerProps;
  const explorerRows = Object.values(explorer.values).some(value => value === "all") ? []
    : explorerProps.sourceRows.filter(row => row.country === explorer.values.country && row.source_id === explorer.values.source_id
      && String(row.year) === String(explorer.values.year) && row.genre_scope === explorer.values.genre_scope && row.format_label === explorer.values.format_label
      && (explorerQueryId !== listenerQueryId || row.record_type === "genre"));
  const explorerMetadata = explorerRows[0];
  const profileAvailable = sourceRows.filter(row => row.genre_scope === explorer.values.genre_scope && row.format_label === explorer.values.format_label && Number.isFinite(row.participation));
  const latestExplorerYear = profileAvailable.length ? Math.max(...profileAvailable.map(row => row.year)) : null;
  const checks = queries.data_freshness?.rows ?? [];
  const explorerCheck = checks.find(row => row.source_id === explorer.values.source_id);
  const currentYear = new Date().getUTCFullYear();
  const explorerControls = <Filters {...explorer.filterProps} filters={[]}>
    <Dropdown label="Country" showLabel value={explorer.values.country} choices={countries}
      allLabel="Choose one country" onChange={value => explorer.setFilter("country", value)} />
    <Dropdown label="Survey source" showLabel value={explorer.values.source_id} choices={sourceChoices} choiceLabels={sourceLabels}
      allLabel="Choose one source" onChange={value => explorer.setFilter("source_id", value)} />
    <Dropdown label="Observation year" showLabel value={explorer.values.year} choices={yearChoices}
      allLabel="Choose one year" onChange={value => explorer.setFilter("year", value)} />
    <Dropdown label="Genre question" showLabel value={explorer.values.genre_scope} choices={questionChoices}
      allLabel="Choose one question" onChange={value => explorer.setFilter("genre_scope", value)} />
    <Dropdown label="Format" showLabel value={explorer.values.format_label} choices={formatChoices}
      allLabel="Choose one format" onChange={value => explorer.setFilter("format_label", value)} />
  </Filters>;
  const listenerCountries = choicesFor(listenerOriginal, "country");
  const listenerScope = useSectionFilters([
    { id: "country", label: "Listener study country", field: "country", defaultValue: listenerCountries.includes("Sweden") ? "Sweden" : listenerCountries[0] ?? "all", queryIds: ["storytel_audio_2026"] },
  ], {}, { rowId: "atlas:genres:listeners", componentIds: ["genre-listener-study"], label: "2026 listener study country" });
  const listenerProps = listenerScope.componentProps("storytel_audio_2026", ["country", "year", "record_type", "genre"]);
  const listenerRows = listenerScope.values.country === "all" ? []
    : listenerProps.sourceRows.filter(row => row.country === listenerScope.values.country && row.record_type === "genre");
  const listenerMetadata = listenerRows[0];
  const listenerCheck = checks.find(row => row.source_id === listenerMetadata?.source_id);
  const genreCountryCount = countries.length;
  const listenerControls = <Filters {...listenerScope.filterProps} filters={[]}>
    <Dropdown label="Listener study country" showLabel value={listenerScope.values.country} choices={listenerCountries}
      allLabel="Choose one country" onChange={value => listenerScope.setFilter("country", value)} />
  </Filters>;
  const originalCanada = (queries[historyQueryId]?.rows ?? []).filter(row => row.country_iso3 === "CAN");
  const genreYears = surveyYearChoices(originalCanada);
  const scope = useSectionFilters([
    { id: "genre_scope", label: "Genre scope", field: "genre_scope", defaultValue: "Book fiction genres", queryIds: [historyQueryId] },
    { id: "year", label: "Survey year", field: "year", defaultValue: genreYears[0] ?? "all", queryIds: [historyQueryId] },
  ], {}, { rowId: "atlas:genres:canada", componentIds: ["canada-genre-profile"], label: "Canadian book genre filters" });
  const scoped = scope.componentProps(historyQueryId, ["year", "genre", "format_label"]);
  const canada = scope.values.genre_scope === "all" || scope.values.year === "all" ? []
    : scoped.sourceRows.filter(row => row.country_iso3 === "CAN" && String(row.year) === String(scope.values.year));
  const singapore = reviewedRows("genre_profiles", ["genre", "format_label"]).filter(row => row.country_iso3 === "SGP");
  const heatmap = { type: "heatmap", x: "format_label", y: RATE, series: "genre", showValues: true,
    missingValues: "gap", colorDomain: [0, 100], colorScaleStartAtZero: true, rowHeight: 35,
    showXAxisLabel: false, showYAxisLabel: false, valueDecimals: 0, stackable: false };
  const genreControls = <Filters {...scope.filterProps} filters={[]}><Dropdown label="Genre scope" showLabel
    value={scope.values.genre_scope} choices={["Book fiction genres", "Book non-fiction genres"]}
    allLabel="Choose one scope" onChange={value => scope.setFilter("genre_scope", value)} />
    <Dropdown label="Survey year" showLabel value={scope.values.year} choices={genreYears}
      allLabel="Choose one year" onChange={value => scope.setFilter("year", value)} /></Filters>;
  return <>
    <Note>All {genreCountryCount} countries with reviewed genre evidence are available in the country selector below. Choose a country, survey source and observation year. Each study keeps its original question and population.</Note>
    <SortableRegion id="atlas:genres:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:genres:explorer", items: ["genre-country-explorer"], header: <SectionHeader id="genres-explorer-heading" title="Genre evidence by country and survey" filters={explorerControls} /> },
      { id: "atlas:genres:listeners", items: ["genre-listener-study"], header: <SectionHeader id="genres-listeners-heading" title="2026 audiobook listener study" filters={listenerControls} /> },
      { id: "atlas:genres:canada", items: ["canada-genre-profile"], header: <SectionHeader id="genres-canada-heading" title={`Canada: book genres${scope.values.year !== "all" ? `, ${scope.values.year}` : ""}`} filters={genreControls} /> },
      { id: "atlas:genres:singapore", items: ["singapore-genre-profile"], header: <SectionHeader id="genres-singapore-heading" title="Singapore: broader reading genres, 2024" /> },
    ]}>
      <Block id="genre-country-explorer" title="Genres within one reviewed study" span={12}>
        <Plot id="genre-country-explorer" queryId={explorerQueryId} title="Genres within one reviewed study"
          rows={explorerRows} spec={bar("genre", { sortOrder: "descending" })} height={Math.max(300, Math.min(800, explorerRows.length * 32))}
          {...explorerProps} sourceRows={explorerRows}>
          {explorerMetadata ? <div className="atlas-profile-context" data-reviewed-rows><dl>
            <div><dt>Country and chart observation</dt><dd>{explorerMetadata.country}, {explorerMetadata.year}</dd></div>
            <div><dt>Survey source</dt><dd>{sourceLabels[explorerMetadata.source_id] ?? explorerMetadata.source_id}</dd></div>
            <div><dt>Genre question and format</dt><dd>{explorerMetadata.genre_scope}; {explorerMetadata.format_label}</dd></div>
            <div><dt>Survey base</dt><dd>{[...new Set(explorerRows.map(row => row.denominator))].join("; ")}</dd></div>
            <div><dt>Reference population</dt><dd>{[...new Set(explorerRows.map(row => row.population))].join("; ")}</dd></div>
            <div><dt>Recall period</dt><dd>{[...new Set(explorerRows.map(row => row.period))].join("; ")}</dd></div>
            <div><dt>Latest available observation</dt><dd>{latestExplorerYear ?? "Unavailable"}</dd></div>
            <div><dt>Source checked</dt><dd>{fmtChecked(explorerCheck?.last_checked_at)} (UTC)</dd></div>
          </dl></div> : <Note>Select one country, source, year, question and format to view its published results.</Note>}
          {latestExplorerYear && !profileAvailable.some(row => row.year === currentYear) ? <Note>No reviewed observation for {currentYear} in this survey profile. The latest available observation is {latestExplorerYear}; missing years are not estimated.</Note> : null}
          {explorerQueryId === listenerQueryId && <Note>April 2026 study commissioned by Storytel and conducted by Trackit Insight. Only the five published genres per country are available. Results describe audiobook listeners, not national reach or Storytel customers. Unlisted options are unreported, not zero.</Note>}
          <Note tone="caution">Genre percentages retain each survey's denominator and response rules. They are not market shares. Different surveys are not combined into a country ranking. {explorerMetadata?.notes}</Note>
          {explorerRows.some(row => !Number.isFinite(row.participation)) && <Note>Unreported genre percentages remain missing in the source rows.</Note>}
        </Plot>
      </Block>
      <Block id="genre-listener-study" title="Audiobook genres among surveyed listeners" span={12}>
        {queries.storytel_audio_2026 ? <Plot id="genre-listener-study" queryId="storytel_audio_2026" title="Audiobook genres among surveyed listeners"
          rows={listenerRows} spec={bar("genre", { sortOrder: "descending", colors: { [RATE]: "var(--chart-2)" } })} height={300}
          {...listenerProps} sourceRows={listenerRows}>
          {listenerMetadata ? <div className="atlas-profile-context" data-reviewed-rows><dl>
            <div><dt>Country and observation year</dt><dd>{listenerMetadata.country}, {listenerMetadata.year}</dd></div>
            <div><dt>Survey base</dt><dd>{listenerMetadata.denominator}</dd></div>
            <div><dt>Reference population</dt><dd>{listenerMetadata.population}</dd></div>
            <div><dt>Recall period</dt><dd>{listenerMetadata.period}</dd></div>
            <div><dt>Latest available observation / source check</dt><dd>{listenerMetadata.year} / {fmtChecked(listenerCheck?.last_checked_at)} (UTC)</dd></div>
          </dl></div> : <Note>Select one listener study country.</Note>}
          <Note tone="caution">April 2026 study commissioned by Storytel and conducted by Trackit Insight. Results describe audiobook listeners, not national reach or Storytel customers. Only the five published genres per country are available. Multiple responses can overlap; unlisted options are unreported, not zero.</Note>
        </Plot> : null}
      </Block>
      <Block id="canada-genre-profile" title="Genres by book format" span={12}>
        {queries[historyQueryId] ? <Plot id="canada-genre-profile" queryId={historyQueryId} title="Genres by book format" rows={canada}
          spec={heatmap} height={460} {...scoped} sourceRows={canada}>
          <Note tone="caution">English-speaking adult internet panel, unweighted. The denominator is readers of the selected genre scope within each format; exact eligible genre subgroup sample sizes are unpublished. The overall reader panel size is not the genre denominator. Readers could choose up to three genres. Missing values stay unavailable.</Note>
          {!canada.length && <Note>Select one book genre scope and one survey year to view its format profile.</Note>}
        </Plot> : <DataComponent variant="card" id="canada-genre-profile" queryId="sources" title="Genres by book format" kind="custom" displayRows={[]} sourceRows={[]}><Note>Genre extracts are pending verification.</Note></DataComponent>}
      </Block>
      <Block id="singapore-genre-profile" title="Fiction genres across mixed reading materials" span={12}>
        {queries.genre_profiles ? <Plot id="singapore-genre-profile" queryId="genre_profiles" title="Fiction genres across mixed reading materials" rows={singapore}
          spec={bar("genre", { sortOrder: "descending", colors: { [RATE]: "var(--chart-3)" } })} height={280}>
          <Note tone="caution">General readers (n=3,657), citizens and permanent residents age 20+. “Usually” has no fixed annual recall. This question includes websites, social media, books, ebooks and magazines. It cannot be compared directly with Canada’s book-only profile.</Note>
        </Plot> : null}
      </Block>
    </SortableRegion>
  </>;
}

function CoverageMap({ rows }) {
  const [focused, setFocused] = useState(null);
  const byCountry = new Map(rows.map(row => [row.country_iso3, row]));
  const focusRow = focused ? byCountry.get(focused.iso3) : null;
  const counts = Object.keys(statusColors).map(status => ({ status, count: rows.filter(row => row.audit_status === status).length }));
  return <div className="atlas-map" data-reviewed-rows>
    <svg viewBox="0 0 1000 460" className="atlas-world" role="group" aria-label="World map of source readiness">
      {worldCountries.map(country => {
        const row = byCountry.get(country.iso3);
        const description = `${row?.country ?? country.name}: ${row?.audit_status ?? "Outside this filter or absent from ISO roster"}`;
        return <path key={country.iso3 + country.name} d={country.path} fill={row ? statusColors[row.audit_status] ?? statusColors["Not researched"] : "var(--muted)"}
          stroke="var(--surface)" strokeWidth="0.6" role="button" tabIndex={0} aria-label={description}
          onPointerEnter={() => setFocused(country)} onFocus={() => setFocused(country)} onClick={() => setFocused(country)}
          onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setFocused(country); } }}>
          <title>{description}</title>
        </path>;
      })}
    </svg>
    <div className="atlas-map-detail" aria-live="polite">
      {focused ? <><strong>{focusRow?.country ?? focused.name}</strong><span>{focusRow?.audit_status ?? "Outside current filter or absent from ISO roster"}</span>
        {focusRow?.research_gap && <span>{focusRow.research_gap}</span>}</> : <><strong>Source readiness</strong><span>Hover or focus a country to inspect its audit status.</span></>}
    </div>
    <ul className="atlas-map-legend">{counts.map(({ status, count }) => <li key={status}><i style={{ background: statusColors[status] }} /><span>{status}</span><strong>{count}</strong></li>)}</ul>
    <Note>Readiness describes this project’s audit, not how much people read. Natural Earth 1:110m boundaries use an equirectangular projection. Small territories are omitted at this map scale; the complete 249-country and territory roster is searchable below.</Note>
  </div>;
}

function Coverage() {
  const { reviewedRows } = useDataApp();
  const scope = useSectionFilters([
    { id: "status", label: "Audit status", field: "audit_status", defaultValue: "all", queryIds: ["coverage"] },
  ], {}, { rowId: "atlas:coverage:readiness", componentIds: ["coverage-map", "coverage-roster"], label: "Coverage audit filters" });
  const scoped = scope.componentProps("coverage", ["country"]);
  const rows = scoped.sourceRows;
  const sources = reviewedRows("sources", ["source_id"]);
  const columns = [
    { field: "country", label: "Country / territory", presentation: "identity", secondaryField: "country_iso3" },
    { field: "audit_status", label: "Audit status", presentation: "status" },
    { field: "book_participation", label: "Book participation" },
    { field: "audiobook_separate", label: "Audio measured separately" },
    { field: "genre_detail", label: "Genre evidence" },
    { field: "research_gap", label: "Remaining gap" },
  ];
  const sourceColumns = [
    { field: "title", label: "Source", presentation: "identity", secondaryField: "provider" },
    { field: "review_status", label: "Status" },
    { field: "survey_year", label: "Year" },
    { field: "population", label: "Population" },
    { field: "comparability_notes", label: "Interpretation" },
    { field: "source_url", label: "Original", renderCell: value => value ? <SourceLink url={value}>Open source ↗</SourceLink> : "Unavailable" },
  ];
  return <>
    <Note>Worldwide scope means a complete country and territory roster with visible evidence gaps. No global participation rate is calculated.</Note>
    <SortableRegion id="atlas:coverage:canvas" variant="canvas" spacing="standard" columns={12} rows={[
      { id: "atlas:coverage:readiness", items: ["coverage-map", "coverage-roster"], header: <SectionHeader id="coverage-readiness-heading" title="Worldwide evidence coverage" filters={<Filters {...scope.filterProps} />} /> },
      { id: "atlas:coverage:sources", items: ["source-register"], header: <SectionHeader id="coverage-sources-heading" title="Public source register" /> },
    ]}>
      <Block id="coverage-map" title="Source readiness around the world" span={12} kind="custom">
        <DataComponent variant="card" id="coverage-map" queryId="coverage" title="Source readiness around the world" kind="custom"
          {...scoped} displayRows={rows} sourceRows={rows} description="Country audit status joined to actual Natural Earth geographic boundaries. Geometry is context; audit rows are the reviewed evidence.">
          <CoverageMap rows={rows} />
        </DataComponent>
      </Block>
      <Block id="coverage-roster" title="Country and territory evidence lookup" span={12} kind="table">
        <DataComponent variant="card" id="coverage-roster" queryId="coverage" title="Country and territory evidence lookup" kind="table" {...scoped}>
          <DataTable rows={rows} columns={columns} label="Complete country and territory audit" rowKey="country_iso3" />
        </DataComponent>
      </Block>
      <Block id="source-register" title="Source definitions and access" span={12} kind="table">
        <DataComponent variant="card" id="source-register" queryId="sources" title="Source definitions and access" kind="table" displayRows={sources} sourceRows={sources}>
          <DataTable rows={sources} columns={sourceColumns} label="Public source register with definitions and links" rowKey="source_id" />
        </DataComponent>
      </Block>
    </SortableRegion>
  </>;
}
