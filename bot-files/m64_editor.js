// m64 header information source: http://tasvideos.org/EmulatorResources/Mupen/M64.html

var fs = require(`fs`)
var save = require(`./save.js`)
const cp = require(`child_process`)
const process = require(`process`)
const request = require(`request`)

// The following are used for the encoding command
// They will need to be manually set before running an instance of the bot
const MUPEN_PATH = "B:/Mupen64/1.0.7_2/"
const MUPEN_NAME = "mupen64_1_8_0_encoding_fixed.exe "
const LUA = `-lua "B:\\Mupen64\\Lua\\Encode\\inputs.lua" `
const GAME_PATH = "B:/Mupen64/" // all games will be run with GAME_PATH + game + .z64 (hardcoded J to run with .n64)
const KNOWN_CRC = { // supported ROMS (TODO: add common romhacks)
  "FF 2B 5A 63": "U",
  "0E 3D AA 4E": "J",
  "AF 5E 2D 01": "Ghosthack_v2",
  "E2 23 33 F9": "Ghosthack_v3"
}

var EncodingQueue = [] // {st url, m64 url, filename, discord channel id, user id}

// Note: the lua script needs to have a built in failsafe. Sample code:
/*
local MAX_WAIT_TIME = 5 * 30
local timer = 0
local last_frame = -1

function autoexit()
    if emu.samplecount() == last_frame then
        timer = timer + 1
    end
    last_frame = emu.samplecount()
    if timer == MAX_WAIT_TIME then
        f = io.open("encode_failed.txt", "w")
        io.close(f)
        os.exit() 
    end
end

emu.atinput(autoexit)
*/


// intToLittleEndian(int, int)
// returns a buffer containing the base 10 int in little endian form
// Ex: intToLittleEndian(7435, 4) => <0b 1d 00 00>
function intToLittleEndian(int, byteLength) {
  var hex = int.toString(16).toUpperCase()              // convert to hex
  while (hex.length < 2 * byteLength) hex = `0` + hex   // fill the size
  var bytes = hex.match(/.{2}/g)                        // split into pairs
  var reverse = []
  bytes.forEach(byte => reverse.unshift(`0x` + byte))   // reverse order
  return Buffer.from(reverse)                           // convert to buffer
}

// littleEndianToInt(Buffer)
// converts a buffer in little endian to an int in base 10
// Ex: littleEndianToInt(<0b 1d 00 00>) => 7435
function littleEndianToInt(buffer) {
  var hex = ``
  var array = [...buffer]
  array.forEach(byte => {
    byte = byte.toString(16).toUpperCase() // force hex
    if (byte.toString().length < 2) {
      hex = `0` + byte + hex
    } else {
      hex = byte + hex
    }
  })
  return parseInt(hex, 16)
}

// bufferToString(Buffer)
// converts a buffer to a string and removes trailing zeros
function bufferToString(buffer) {
  while (Buffer.byteLength(buffer) > 0 && buffer[Buffer.byteLength(buffer) - 1] == 0) {
    buffer = buffer.slice(0, Buffer.byteLength(buffer) - 1)
  }
  return buffer.toString()
}

// bufferToStringLiteral(Buffer)
// displays a buffer as a string
// Ex: bufferToStringLiteral(<58 61 6E 64 65 72>) => "58 61 6E 64 65 72"
function bufferToStringLiteral(buffer) {
  var result = ``
  var array = [...buffer]
  array.forEach(byte => {
    byte = byte.toString(16).toUpperCase() // force hex
    result += byte.padStart(2, "0") + ` `
  })
  return result.substring(0, result.length - 1)
}

// bufferInsert(Buffer, int, int, Buffer)
// inclusive lower bound, exclusive upper bound
// Ex: bufferInsert(<00 01 02 03 04>, 2, 4, <06, 09>) => <00, 01, 06, 09, 04>
function bufferInsert(buffer, start, end, insert) {
  return Buffer.concat([
    buffer.slice(0, start),
    insert,
    buffer.slice(end, Buffer.byteLength(buffer))
  ])
}

// check if a file has been fully downloaded
function hasDownloaded(filename, filesize) {
  try {
    var file = fs.readFileSync(save.getSavePath() + "/" + filename)
    return file.byteLength == filesize
  } catch (e) {
    return false
  }
}

// TODO: give the call back a variable amount of args
// run a callback function when a file downloads
function onDownload(filename, filesize, callback) {
  if (!hasDownloaded(filename, filesize)) {
    setTimeout(() => {onDownload(filename, filesize, callback)}, 1000) // recursive call after 1s
  } else {
    callback(filename)
  }
}

// repeated code. allows for url/filename/size to be entered manually,
// it will use the attachment's properties if they arent passed
function downloadAndRun(attachment, callback, url, filename, filesize) {
  if (!url) url = attachment.url
  if (!filename) filename = attachment.filename
  if (!filesize) {
    if (attachment) {
      filesize = attachment.size
    } else {
      request({url:url, method: `HEAD`}, (err, response) => { // find the filesize
        save.downloadFromUrl(url, save.getSavePath() + `/` + filename)
        onDownload(filename, response.headers[`content-length`], callback)
      })
      return
    }
  }

  save.downloadFromUrl(url, save.getSavePath() + `/` + filename)
  onDownload(filename, filesize, callback)
}


module.exports = {
	name: `m64 Editor`,
	short_name: `m64`,

  rerecords:{
    name: `rerecords`,
    aliases: [`rerecord`, `rr`],
    short_descrip: `Change rerecord amount`,
    full_descrip: `Usage: \`$rr <num_rerecords> <m64 attachment>\`\nChanges the rerecords count in the attached m64. If the number provided is less than 0, it will edit it to be 0. If it exceeds the maximum 4-byte integer (4294967295) then it will edit it to be the max.`,
    hidden: true,
    function: async function(bot, msg, args) {

      // make sure there's enough arguments
      if (args.length == 0) {
        return `Missing Arguments: \`$rr <num_rerecords> <m64 attachment>\``
      } else if (msg.attachments.length == 0) {
        return `Missing Arguments: No m64 specified \`$rr <num_rerecords> <m64 attachment>\``
      } else if (isNaN(args[0])) {
        return `Invalid Argument: rerecords must be a number`
      } else if (!msg.attachments[0].url.endsWith(`.m64`)) {
        return `Invalid Argument: file is not an m64`
      }

      // force rerecords in range of [0, 4 byte max]
      const MAX_RR = parseInt(0xFFFFFFFF)
      const LOCATION = parseInt(0x10)
      const SIZE = 4

      var rerecords = parseInt(args[0])
      if (rerecords > MAX_RR) {
        rerecords = MAX_RR
        bot.createMessage(msg.channel.id, `WARNING: Max rerecord count exceeded`)
      } else if (rerecords < 0) {
        rerecords = 0
        bot.createMessage(msg.channel.id, `WARNING: Min rerecord count exceeded`)
      }

      function updateRerecords(filename) {
        fs.readFile(save.getSavePath() + `/` + filename, async (err, m64) => {
          if (err) {
            bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
          } else {

            var rr_hex = intToLittleEndian(rerecords, SIZE)
            var old_rr = littleEndianToInt(m64.slice(LOCATION, LOCATION + SIZE))
            var new_m64 = bufferInsert(m64, LOCATION, LOCATION + SIZE, rr_hex)

            try {
              await bot.createMessage(
                msg.channel.id,
                `Rerecords changed from ${old_rr} to ${rerecords}`,
                {file: new_m64, name: filename}
              )
              fs.unlinkSync(save.getSavePath() + `/` + filename)
            } catch (err) {
              bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
            }
          }
        })
      }

      downloadAndRun(msg.attachments[0], updateRerecords)

    }
  },

  description:{
    name: `description`,
    aliases: [`descrip`],
    short_descrip: `Edit description`,
    full_descrip: `Usage: \`$descrip [new description] <m64 attachment>\`\nChanges the description in the attached m64. Spaces are allowed in the new description.`,
    hidden: true,
    function: async function(bot, msg, args) {

      if (msg.attachments.length == 0) {
        return `Missing Arguments: No m64 specified \`$descrip [new description] <m64 attachment>\``
      } else if (!msg.attachments[0].url.endsWith(`.m64`)) {
        return `Invalid Argument: file is not an m64`
      }

      const LOCATION = parseInt(0x300)
      const SIZE = 256

      var descrip = Buffer.from(args.join(` `), `utf8`)
      if (Buffer.byteLength(descrip) > SIZE) {
        descrip = descrip.slice(0, SIZE)
        bot.createMessage(msg.channel.id, `WARNING: Max length exceeded`)
      }
      while (Buffer.byteLength(descrip) < SIZE) { // force to fill
        descrip = Buffer.concat([descrip, Buffer.from([0])])
      }

      function updateDescrip(filename) {
        fs.readFile(save.getSavePath() + `/` + filename, async (err, m64) => {
          if (err) {
            bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
          } else {

            var old_descrip = m64.slice(LOCATION, LOCATION + SIZE)
            var new_m64 = bufferInsert(m64, LOCATION, LOCATION + SIZE, descrip)

            try {
              await bot.createMessage(
                msg.channel.id,
                `Description changed from \`${bufferToString(old_descrip)}\` to \`${bufferToString(descrip)}\``,
                {file: new_m64, name: filename}
              )
              fs.unlinkSync(save.getSavePath() + `/` + filename)
            } catch (err) {
              bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
            }
          }
        })
      }

      downloadAndRun(msg.attachments[0], updateDescrip)

    }
  },

  author:{
    name: `author`,
    aliases: [`authors`, `auth`],
    short_descrip: `Edit athor's name`,
    full_descrip: `Usage: \`$auth [new name] <m64 attachment>\`\nChanges the author in the attached m64 file. You can uses spaces in the new name.`,
    hidden: true,
    function: async function(bot, msg, args) {

      if (msg.attachments.length == 0) {
        return `Missing Arguments: No m64 specified \`$auth [new name] <m64 attachment>\``
      } else if (!msg.attachments[0].url.endsWith(`.m64`)) {
        return `Invalid Argument: file is not an m64`
      }

      const LOCATION = parseInt(0x222)
      const SIZE = 222
      var author = Buffer.from(args.join(` `), `utf8`)
      if (Buffer.byteLength(author) > SIZE) {
        author = author.slice(0, SIZE)
        bot.createMessage(msg.channel.id, `WARNING: Max length exceeded`)
      }
      while (Buffer.byteLength(author) < SIZE) { // force to fill
        author = Buffer.concat([author, Buffer.from([0])])
      }

      function updateAuthor(filename) {
        fs.readFile(save.getSavePath() + `/` + filename, async (err, m64) => {
          if (err) {
            bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
          } else {

            var old_author = m64.slice(LOCATION, LOCATION + SIZE)
            var new_m64 = bufferInsert(m64, LOCATION, LOCATION + SIZE, author)

            try {
              await bot.createMessage(
                msg.channel.id,
                `Author changed from \`${bufferToString(old_author)}\` to \`${bufferToString(author)}\``,
                {file: new_m64, name: filename}
              )
              fs.unlinkSync(save.getSavePath() + `/` + filename)
            } catch (err) {
              bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
            }
          }
        })
      }

      downloadAndRun(msg.attachments[0], updateAuthor)

    }
  },

  info:{
    name: `m64info`,
    aliases: [`m64header`],
    short_descrip: `Reads important header data`,
    full_descrip: `Usage: \`$m64info <m64 attachment>\`\nReads the authors, description, rerecords, and ROM CRC.`,
    hidden: true,
    function: async function(bot, msg, args) {

      if (msg.attachments.length == 0) {
        return `Missing Arguments: No m64 specified \`$m64info <m64 attachment>\``
      } else if (!msg.attachments[0].url.endsWith(`.m64`)) {
        return `Invalid Argument: file is not an m64`
      }

      function info(filename) {
        fs.readFile(save.getSavePath() + `/` + filename, async (err, m64) => {
          if (err) {
            bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
          } else {
            var author = bufferToString(m64.slice(0x222, 0x222 + 222))
            var descrip = bufferToString(m64.slice(0x300, 0x300 + 256))
            var rr = littleEndianToInt(m64.slice(0x10, 0x10 + 4))
            var crc = m64.slice(0xE4, 0xE4 + 4)
            crc = bufferToStringLiteral(crc.reverse()) // reverse
            var rom = "?"
            if (crc in KNOWN_CRC) rom = KNOWN_CRC[crc]

            var result = `Author(s): ${author}\n`
            result += `Description: ${descrip}\n`
            result += `Rerecords: ${rr}\n`
            result += `ROM: ${crc} (${rom})`

            try {
              await bot.createMessage(msg.channel.id, result)
              fs.unlinkSync(save.getSavePath() + `/` + filename)
            } catch (err) {
              bot.createMessage(msg.channel.id, `Something went wrong\`\`\`${err}\`\`\``)
            }
          }
        })
      }

      downloadAndRun(msg.attachments[0], info)

    }
  },

  encode:{
    name: `encode`,
    aliases: [`record`],
    short_descrip: `Encode an m64`,
    full_descrip: `Usage: \`$encode <link to m64> <link to st>\`\nDownloads the files, makes an encode, and uploads the recording. [BETA]`,
    hidden: true,
    function: async function(bot, msg, args) {

      return `This command is currently disabled` // exit because I dont want the bot on my linux server to update and try and run this command

      // How this works:
      // 1. Download m64
      // 2. Download st
      // 3. Run mupen with -avi and -m64 commands
      // 4. Once avi capture is done, delete "encode.m64/st"
      //    Note: this uses the emulator closing as the sign to continue
      //          This needs some way to ensure the emulator closes (possibly a lua script forcing it closed?)
      // 5. Upload avi capture named "encode.mp4"
      //    a) use ffmpeg to convert
      // 6. Delete "encode.mp4"

      // ToDo: be generous with user input (st link + m64 attachment, st/m64 in any order, etc.)
      //       Detect rom and play U or J
      //       add a queuing system

      if (args.length < 2) {
        return `Missing Arguments: \`$encode <link to m64> <link to st>\``
      } else if (!args[0].endsWith(`.m64`)) {
        return `Invalid Argument: 1st file is not an m64`
      } else if (!args[1].endsWith(`.st`)) {
        return `Invalid Argument: 2nd file is not an st`
      }

      var m64_url = args[0]
      var st_url = args[1]
      var filename = m64_url.split(`/`) // ensure contains / ?
      filename = filename[filename.length - 1]
      filename = filename.substring(0, filename.length - 4)


      function NextEncode(ping = true, delayed_retry = true) {
        if (EncodingQueue.length == 0 || EncodingQueue[0].processing) {
          return // nothing to encode, or needs to wait
        }

        var encode = EncodingQueue[0] // using this in the following functions instead of parameters is cringe
        EncodingQueue[0].processing = true // don't remove right away so new encoding requests don't try to run at the same time

        function runMupen() {
          //bot.createMessage(encode.channel_id, `Encoding...`)
          if (fs.existsSync(`./encode.avi`)) fs.unlinkSync(`./encode.avi`) // remove previous encode
          if (fs.existsSync(`./encode.mp4`)) fs.unlinkSync(`./encode.mp4`)
          
          // auto detect game
          var m64 = fs.readFileSync(save.getSavePath() + `/encode.m64`) // no error handling. This file should exist.
          var crc = m64.slice(0xE4, 0xE4 + 4)
          crc = bufferToStringLiteral(crc.reverse())
          if (crc in KNOWN_CRC == false) {
            bot.createMessage(encode.channel, `<@${encode.user}> Unknown CRC: ${crc}. For a list of supported games, use $ListCRC`)
            return
          }
          
          const GAME = `-g "${GAME_PATH}${KNOWN_CRC[crc]}.${KNOWN_CRC[crc] == `J` ? `n` : `z`}64" `
          const M64 = `-m64 "${process.cwd() + save.getSavePath().substring(1)}/encode.m64" `
          const AVI = `-avi "encode.avi"`
          
          var Mupen = cp.exec(MUPEN_PATH + MUPEN_NAME + GAME + M64 + AVI + LUA) // 3
          
          /*if (ping) { // one ping is bad enough, but maybe this is a good idea?
            bot.createMessage(encode.channel, `<@${encode.user}> your encode is being processed`).catch(
              err => console.log(`Failed Encode Processing Message` + err)
            )
          }*/
  
          Mupen.on('close', (code, signal) => { // 4

            if (fs.existsSync(MUPEN_PATH + `encode_failed.txt`)) {
              bot.createMessage(encode.channel, `Failed to playback m64 (CRC: ${crc}, ${KNOWN_CRC[crc]}). Could not encode <@${encode.user}>`)
              fs.unlinkSync(MUPEN_PATH + `encode_failed.txt`)
              NextEncode(true, true)
              return
            }

            bot.createMessage(encode.channel, `Uploading...`)
            cp.execSync(`ffmpeg -i encode.avi encode.mp4`)
            fs.readFile(`./encode.mp4`, async (err, mp4) => {
              try {
                let reply = ping ? `Encode Complete <@${encode.user}>` : `Encode Complete`
                await bot.createMessage(encode.channel, reply, {file: mp4, name: `${encode.filename}.mp4`}) // 5
                fs.unlinkSync(`./encode.mp4`)
              } catch (err) {
                bot.createMessage(encode.channel, `Something went wrong <@${encode.user}> \`\`\`${err}\`\`\``)
              }
              EncodingQueue.shift() // now it's safe to remove this from the queue
              NextEncode(true, true)
            })
          })
        }

        function downloadST() {
          downloadAndRun(undefined, runMupen, encode.st, `encode.st`) // 2 -> 3
        }
  
        downloadAndRun(undefined, downloadST, encode.m64, `encode.m64`) // 1 -> 2

        // have a 1 time delay to check again in 5s (i dont trust asyncronous bs, but if it skips something twice I'll be damned)
        if (delayed_retry) {
          setTimeout(() => NextEncode(true, false), 5000)
        }
        
        return
      }

      function AddToEncodingQueue(m64_url, st_url, filename, channel_id, user_id) {
        // add to queue
        EncodingQueue.push({
          m64: m64_url,
          st: st_url,
          filename: filename,
          channel: channel_id,
          user: user_id,
          processing: false
        })


        if (EncodingQueue.length == 1) {
          NextEncode(false, true)
          return "Queue position 0: your encode is processing..."
        } else if (EncodingQueue.length == 2) {
          return "Queue position 1: your encode will be processed next"
        } else {
          return `Queue position ${EncodingQueue.length - 1}`
        }
      }

      

      return AddToEncodingQueue(m64_url, st_url, filename, msg.channel.id, msg.author.id)

    }
  }
}
