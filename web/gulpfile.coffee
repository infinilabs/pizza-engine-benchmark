gulp = require 'gulp'
browserify = require 'gulp-browserify'
concat = require 'gulp-concat'
serve = require 'gulp-serve'
watch = require 'gulp-watch'
less = require 'gulp-less'
cjsx = require "gulp-cjsx"

gulp.task 'watch', ->
    watch '**.coffee', ->
      gulp.start("scripts")
    watch '**.cjsx', ->
      gulp.start("scripts")
    watch '**.less', ->
      gulp.start("stylesheet")


gulp.task 'serve', serve('output')
#
# gulp.task 'cjsx', ->
#     gulp.src('./index.cjsx')
#       .pipe(cjsx({bare: true}))
#       .pipe(gulp.dest('./output/'))

gulp.task 'stylesheet', ->
  gulp.src('./style.less')
    .pipe(less())
    .pipe(gulp.dest('./output/'))

gulp.task 'scripts', ->
  console.log "build scripts"
  gulp
    .src('./index.cjsx', { read: false })
    .pipe(browserify {transform: ['coffee-reactify'], extensions: ['.coffee', '*.cjsx']})
    .pipe(concat 'index.js')
    .pipe(gulp.dest('./output/'))

gulp.task 'default', ->
  gulp.run 'scripts'

gulp.task('default', ['watch', 'serve']);
