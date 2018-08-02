$ = require "jquery"
React = require "react"
ReactDOM = require "react-dom"

formatPercentVariation = (p)->
  if p?
    "+" + (p * 100).toFixed(1) + " %"
  else
    ""

numberWithCommas = (x)->
    x = x.toString()
    pattern = /(-?\d+)(\d{3})/
    while pattern.test(x)
        x = x.replace(pattern, "$1,$2")
    x

stats = (timings)->
  median = timings[(timings.length / 2) | 0]
  mean = timings.reduce( ((pv, cv)-> pv+cv), 0) / timings.length
  {
    "median": median
    "mean": mean
    "min": timings[0]
    "max": timings[timings.length - 1]
  }

aggregate = (query)->
  res = stats(query.duration)
  res.query = query.query
  res

class Benchmark extends React.Component

  constructor: ->
    @state =
      mode: "COUNT"
      tag: null

  handleChangeMode: (evt)->
    @setState {mode: evt.target.value}

  handleChangeTag: (evt)->
    tag = evt.target.value
    if tag == "ALL"
      @setState {"tag": null}
    else
      @setState {"tag": tag}

  filterQueries: (queries)->
    tag = @state.tag
    if tag?
      queries.filter (query)=>
        0 <= query.tags.indexOf(tag)
    else
      queries

  generateDataView: ->
    engines = {}
    queries = {}
    mode_data = @props.data[@state.mode]
    for engine, engine_queries of mode_data
      engine_queries = @filterQueries engine_queries
      engine_queries = (aggregate(query) for query in engine_queries)
      total = 0
      for query in engine_queries
        total += query.mean
      total = (total / engine_queries.length) | 0
      engines[engine] = total
      for query in engine_queries
        query_data = {}
        if queries[query.query]?
          query_data = queries[query.query]
        query_data[engine] = query
        queries[query.query] = query_data

    for query,query_data of queries
      min_engine = null
      min_microsecs = 0
      max_engine = null
      max_microsecs = 0
      for engine, engine_data of query_data
        if min_engine == null || engine_data.min < min_microsecs
          min_engine = engine
          min_microsecs = engine_data.min
        if max_engine == null || engine_data.min > max_microsecs
          max_engine = engine
          max_microsecs = engine_data.min
      for engine, engine_data of query_data
        if engine != min_engine
          engine_data.variation = (engine_data.min - min_microsecs) / min_microsecs
      query_data[min_engine].className  = "fastest"
      query_data[max_engine].className = "slowest"
    {
      engines: engines
      queries: queries
    }

  render: ->
    data_view = @generateDataView()
    <div>
      <form>
        <fieldset>
          <label htmlFor="collectionField">Collection type</label>
          <select ref= id="collectionField" onChange={ (evt)=> @handleChangeMode(evt)}>
            {
              for mode in @props.modes
                <option value={mode} key={mode}>{mode}</option>
            }
          </select>
          <label htmlFor="queryTagField">Type of Query</label>
          <select id="queryTagField" onChange={ (evt)=>@handleChangeTag(evt)}>
            <option value="ALL" key="all">ALL</option>
            {
              for tag in @props.tags
                <option value={tag} key={tag}>{tag}</option>
            }
          </select>
        </fieldset>
      </form>
      <hr/>
      <table>
        <thead>
        <tr>
          <th>Query</th>
          {
            for engine,engine_stats of data_view.engines
                <th key={"col-" + engine}>{engine}</th>
          }
        </tr>
        </thead>
        <tbody>
          <tr className="average-row">
          <td>AVERAGE</td>
          {
            for engine,engine_stats of data_view.engines
              <td key={"result-" + engine}>
                { numberWithCommas(engine_stats) } μs
              </td>
          }
          </tr>
        {
          i = 0
          for query,engine_queries of data_view.queries
            i+=1
            <tr key={"query" + i}>
              <td>{ query }</td>
              {
                j=0
                for engine,_ of data_view.engines
                  j+=1
                  <td key={"cell"  + i + "-" + j} className={ "data " +engine_queries[engine].className }>
                    <div className="timing">{numberWithCommas(engine_queries[engine].min)}  μs</div>
                    <div className="timing-variation">{ formatPercentVariation(engine_queries[engine].variation) }</div>
                  </td>
              }
            </tr>
        }
        </tbody>
      </table>
    </div>

$ ->
  $.getJSON "results.json", (data)->
    el = document.getElementById("app-container")
    console.log el
    modes = []
    engines = []
    tags_set = {}
    for mode of data
      modes.push mode
    for engine of data[modes[0]]
      engines.push engine
    for query in data[modes[0]][engines[0]]
      for tag in query.tags
        tags_set[tag] = true
    tags = (tag for tag of tags_set)
    tags.sort()
    console.log modes, engines, tags
    ReactDOM.render(<Benchmark data={data} tags={tags} modes={modes} engines={engines} />, el)
