// m64 header information source: http://tasvideos.org/EmulatorResources/Mupen/M64.html

const fs = require(`fs`)
const users = require("./users.js");
const save = require(`./save.js`)
const cp = require(`child_process`)
const process = require(`process`)
const request = require(`request`)

// The following are used for the encoding command
// They will need to be manually set before running an instance of the bot
// Make sure that the manage bad roms (etc.) settings in Mupen are disabled so that romhacks can be run from commandline

// these values are loaded from /saves/m64.json (don't edit them here)
var MUPEN_PATH = "C:\\..."
var LUA_INPUTS = `C:\\MupenServerFiles\\EncodeLua\\inputs.lua`
var LUA_TIME_LIMIT = "B:\\timelimit.lua"
var GAME_PATH = "C:\\..." // all games will be run with GAME_PATH + game + .z64 (hardcoded J to run with .n64)
var KNOWN_CRC = { // supported ROMS // when the bot tries to run the ROMs, it will replace the spaces in the names here with underscores
  //"AF 5E 2D 01": "Ghosthack v2", // depricated
  //"63 83 23 38": "No Speed Limit 64 (Normal)"
}

var EncodingQueue = [] // {st url, m64 url, filename, discord channel id, user id}

// Note: the lua script needs to have a built in failsafe. Sample code:
/*
local f = io.open("maxtimelimit.txt")
local MAX_WAIT_TIME = f:read("*n")
local timer = 0
local last_frame = -1

function autoexit()
    if emu.samplecount() ~= last_frame then
        timer = timer + 1
    end
    last_frame = emu.samplecount()
    if timer == MAX_WAIT_TIME then
        f = io.open("TLE.txt", "w")
        io.close(f)
        os.exit() 
    end
end

emu.atinput(autoexit)
*/

const BitField = 0
const UInt = 1
const Integer = 2 // little endian
const AsciiString = 3
const UTFString = 4
const Bytes = 5

// m64 header information source: http://tasvideos.org/EmulatorResources/Mupen/M64.html
// each entry is offset: [type, byte size, description]
const HEADER = {
  0x000: [Bytes, 4, `Signature: 4D 36 34 1A "M64\\x1A`],
  0x004: [Integer, 4, `Version number (3)`],
  0x008: [Integer, 4, `Movie UID (recording epoch time)`],
  0x00C: [UInt, 4, `Number of VIs`],
  0x010: [UInt, 4, `Rerecord count`],
  0x014: [UInt, 1, `VIs per second`],
  0x015: [UInt, 1, `Number of controllers`],
  //0x016: [UInt, 2, `Reserved (0)`],
  0x018: [Integer, 4, `number of input samples for any controller`],
  0x01C: [UInt, 2, `Movie start type (from snapshot is 1, from power-on is 2)`],
  0x01E: [UInt, 2, `Reserved (0)`],
  0x020: [BitField, 4, `Controllers (from least to most significant, the bits are for controllers 1-4: present, has mempack, has rumblepak)`],
  //0x024: [UInt, 160, `Reserved (0)`],
  0x0C4: [AsciiString, 32, `internal name of ROM used when recording (directly from ROM)`],
  0x0E4: [UInt, 4, `ROM CRC32`],
  0x0E8: [UInt, 2, `ROM country code`],
  //0x0EA: [UInt, 56 `Reserved (0)`],
  0x122: [AsciiString, 64, `Video plugin used when recording`],
  0x162: [AsciiString, 64, `Sound plugin used when recording`],
  0x1A2: [AsciiString, 64, `Input plugin used when recording`],
  0x1E2: [AsciiString, 64, `RSP plugin used when recording`],
  0x222: [UTFString, 222, `Movie author (UTF-8)`],
  0x300: [UTFString, 256, `Movie description (UTF-8)`]
}

// ===============
// Buffer Handling
// ===============

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
function bufferToString(buffer, encoding = "utf8") {
  while (Buffer.byteLength(buffer) > 0 && buffer[Buffer.byteLength(buffer) - 1] == 0) {
    buffer = buffer.slice(0, Buffer.byteLength(buffer) - 1)
  }
  return buffer.toString(encoding)
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

// stringLiteralToBuffer(string, size)
// Converts the string to a buffer
// pads the right with 0 to fill size
// Any non-hex characters are set to F
// Ex: stringLiteralToBuffer("ABG21", 8) => <AB F2 10 00>
function stringLiteralToBuffer(str, size) {
  str = str.toUpperCase().replace(/ /g, ``).replace(/[^0-9A-F]/, `F`)
  if (str.length % 2 == 1) str += `0`
  str = str.match(/.{2}/g)
  var bytes = []
  for (i = (size + (size % 2)) / 2 - 1; i >= 0; i--) {
    if (i < str.length) {
      bytes.unshift(`0x` + str[i])
    } else {
      bytes.unshift(`0x00`)
    }
  }
  return Buffer.from(bytes)
}

function read(addr, file) {
  if (!(addr in HEADER)) return
  var type = HEADER[addr][0]
  var data = file.slice(addr, addr+HEADER[addr][1])

  if (type == BitField) {
    return littleEndianToInt(data).toString(2) // todo: interpret so there's a message like "P1, P2 (mempack), P4 (mempack+rumble)"

  } else if (type == UInt || type == Integer) {
    return littleEndianToInt(data)

  } else if (type == AsciiString) {
    return bufferToString(data, "ascii")

  } else if (type == UTFString) {
    return bufferToString(data)

  } else if (type == Bytes) {
    return bufferToStringLiteral(data)
  }
}

function write(addr, data, file) {
  if (!(addr in HEADER)) return
  var type = HEADER[addr][0]

  if (type == BitField) {
    if (isNaN(data)) {
      data = 1 // default to enable P1
    } else if (isNaN('0b'+data)) {
      data = Number(data)
    } else {
      data = Number('0b'+data) // parseInt(data, 2)
    }
    data = intToLittleEndian(data, HEADER[addr][1])

  } else if (type == UInt) {
    if (isNaN(data) || Number(data) < 0) {
      data = 0
    } else {
      data = Number(data)
    }
    data = intToLittleEndian(data)

  } else if (type == Integer) {
    data = isNaN(data) ? 0 : Number(data)
    data = intToLittleEndian(data)

  } else if (type == AsciiString) {
    data = Buffer.from(data, "ascii")

  } else if (type == UTFString) {
    data = Buffer.from(data)

  } else if (type == Bytes) {
    data = stringLiteralToBuffer(data, HEADER[addr][1])
  }
  bufferInsert(file, addr, addr+HEADER[addr][1], data)
}

// =============
// File Handling (this should be moved to save.js)
// =============

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
    setTimeout(() => callback(filename), 1000) // wait 1s to hope file actually loads??
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


// ===========
// Mupen Queue
// ===========

const DEFAULT_TIME_LIMIT = 5*60*30 // 5 minutes
var previous_time_limit = DEFAULT_TIME_LIMIT + 1
var MupenQueue = []

function NextProcess(bot, retry = true) {
  //console.log(JSON.stringify(MupenQueue))
  if (MupenQueue.length == 0 || MupenQueue[0].process != null) {
    return // nothing to run, or something is currently running
  }
  var request = MupenQueue[0]
  while (request.skip) {
    if (MupenQueue.length == 0) return
    MupenQueue.shift()
    request = MupenQueue[0]
  }
  //console.log(`Running Mupen ${request}`)

  downloadAndRun(
    undefined,
    () => {
      
      // auto detect game
      var m64 = fs.readFileSync(save.getSavePath() + `/tas.m64`)
      var crc = m64.slice(0xE4, 0xE4 + 4)
      crc = bufferToStringLiteral(crc.reverse())
      if (crc in KNOWN_CRC == false) { // what if the user is the bot (internal calls?)
        if (crc == '') {
          // this is a strange case... maybe I'm opening the file too many times in this code?
          // for some reason, retrying immediately (0s delay) has worked every time this error has come up
          if (retry) {
            setTimeout(() => NextProcess(bot, false), 5000) // try again in 5s (just to be safe)
            return
          } else if (request.channel_id == null) {
            console.log(`ERROR: double empty CRC when running Mupen\n${JSON.stringify(request)}`)
          } else {
            bot.createMessage(request.channel_id, `Error: double empty CRC (could not read file?). Please contact an admin`)
          }
        } else if (request.channel_id == null) {
          console.log(`ERROR: unknown CRC ${crc} when running Mupen\n${JSON.stringify(request)}`)
        } else {
          bot.createMessage(request.channel_id, `<@${request.user_id}> Unknown CRC: ${crc}. For a list of supported games, use $ListCRC`)
        }
        MupenQueue.shift() // this request cannot be run
        NextProcess(bot)
        return
      }

      // set timelimit if it's different
      if (request.time_limit != previous_time_limit) {
        // open timelimit.txt and put in the number
        // have timelimit.lua read that number
        previous_time_limit = request.time_limit
      }

      downloadAndRun(
        undefined,
        () => { // run mupen
          
          request.startup()
          const GAME = ` -g "${GAME_PATH}${KNOWN_CRC[crc].replace(/ /g, `_`)}.${KNOWN_CRC[crc] == `Super Mario 64 (JP)` ? `n` : `z`}64" `
          var Mupen = cp.exec(MUPEN_PATH + GAME + request.cmdflags)
          MupenQueue[0].process = Mupen
          Mupen.on(`close`, async (code, signal) => {

            if (fs.existsSync(`TLE.txt`)) { // currently do nothing on time limit exceeded...
              fs.unlinkSync(`TLE.txt`)
              request.callback(true) // pass true if the run timed out
            } else {
              request.callback(false)
            }
            
            MupenQueue.shift()
            NextProcess(bot)
            
          })

        },
        request.st_url,
        "tas.st"
      )

    },
    request.m64_url,
    "tas.m64"
  )
}

// adds a mupen request to the queue. Returns the 0-indexed position of the request
// the m64/st are saved as tas.m64/st
// if you want to run mupen with the -m64 argument that must be explicitly passed here
// startup is called after the download is complete but before mupen is run
// callback is called once the mupen process closes, it is passed whether the time limit was exceeded or not (bool)
// all processes are run with -lua ./timelimit.lua;
// channel_id is used to send a message if no game matches the tas being loaded
// user_id will be pinged if no game matches the tas being loaded (and a valid channel_id is provided)
// Ex. QueueAdd(bot, "...m64", "...st", ["-avi", "encode.avi", "-lua", "C:\\file.lua"], ()=>{}, ()=>{}, 0, 0)
function QueueAdd(bot, m64_url, st_url, cmdline_args, startup, callback, channel_id = null, user_id = null, time_limit = DEFAULT_TIME_LIMIT) {
  //console.log(`Adding ${m64_url}\n${st_url}\n${cmdline_args}\n${channel_id} ${user_id}\n${time_limit}`)
  var cmd = ``
  for (var i = 0; i < cmdline_args.length; ++i) {
    if (cmdline_args[i] == `-lua`) {
      cmd += `-lua "${LUA_TIME_LIMIT};${cmdline_args[++i]}"`
    } else if (cmdline_args[i].startsWith(`-`)) {
      cmd += cmdline_args[i]
    } else {
      cmd += ` "${cmdline_args[i]}" `
    }
  }
  if (!cmdline_args.includes(`-lua`)) {
    cmd += ` -lua "${LUA_TIME_LIMIT}"` // always run a timelimit lua file
  }
  //console.log(`cmd: "${cmd}"`)
  MupenQueue.push({
    m64_url: m64_url, st_url: st_url, cmdflags: cmd,
    startup: startup, callback: callback,
    channel_id: channel_id, user_id: user_id,
    time_limit: time_limit, skip: false, process: null
  })
  //console.log(MupenQueue)
  if (MupenQueue.length == 1) {
    NextProcess(bot)
  }
  return MupenQueue.length
}

// ================
// Discord Commands
// ================

function parseOffset(arg) {
  var offset = parseInt(arg, 16)
  if (isNaN(offset)) {
    return {error: `Invalid Argument: offset must be a number`}
  } else if (!validOffset(offset)) {
    return {error: `Invalid Argument: offset is not a valid start location`}
  }
  return {offset: offset, error: false}
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
    short_descrip: `Edit author's name`,
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

  header:{
    name: `m64header`,
    short_descrip: `List header table`,
    full_descrip: `Usage: \`$header\`\nLists the m64 header table`,
    hidden: true,
    function: async function(bot, msg, args) {
      var result = ``
      Object.keys(HEADER).forEach(offset => {
        result += `0x${parseInt(offset).toString(16).toUpperCase().padStart(2, `0`)} ${HEADER[offset][2]}\n`
      })
      return "```" + result + "```"
    }
  },

  /*m64read:{ // shortcuts for editing m64s
    name: `m64read`,
    aliases: [],
    short_descrip: `read header data`,
    full_descrip: "Usage: `$m64read <offset> <m64>`\nReads header data given an offset and an m64. To see the list of relevant offsets use `$m64header`. An m64 attachment or url (after the address) will be accepted.",
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Argument: `$m64read <address> <m64>`"
      var offset = parseOffset(args.shift())
      if (offset.error) return offset.error
      offset = offset.offset
      
    }
  },

  m64write:{
    name: `m64write`,
    aliases: [],
    short_descrip: ``,
    full_descrip: "Usage: `$m64write <offset> [data] <m64 attachment>`\n.If `[data]` is nothing, an appropriate default value is used. Note: this requires an attachment to be uploaded with the command (sending a url to an m64 won't work).",
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Arguments: "
      var offset = parseOffset(args.shift())
      if (offset.error) return offset.error
      offset = offset.offset


    }
  },

  set_jp:{
    name: ``,
    aliases: [],
    short_descrip: ``,
    full_descrip: ``,
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Argument: "
    }
  },

  set_us:{
    name: ``,
    aliases: [],
    short_descrip: ``,
    full_descrip: ``,
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Argument: "
    }
  },

  startsave:{
    name: ``,
    aliases: [],
    short_descrip: ``,
    full_descrip: ``,
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Argument: "
    }
  },

  startpoweron:{
    name: ``,
    aliases: [],
    short_descrip: ``,
    full_descrip: ``,
    hidden: true,
    function: async function(bot, msg, args) {
      if (args.length < 1) return "Missing Argument: "
    }
  },*/

  info:{
    name: `m64info`,
    aliases: [],
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
    full_descrip: `Usage: \`$encode [cancel/forceskip/queue/nolua] <m64> <st/savestate>\`\nDownloads the files, makes an encode, and uploads the recording.\n\nIf your encode is queued and you want to cancel it, use \`$encode cancel\`.\n\nIf the bot is not processing the queue, contact an admin to use \`$encode ForceSkip\` to skip the encode at the front of the queue (you cannot cancel your own encode if it is currently processing, you will need to use forceskip instead).\n\nPassing the option \`nolua\\no-lua\\disable-lua\` will not run the input visualzing/ram watch lua script (Note: this option must be sent before the links to files)`,
    hidden: true,
    function: async function(bot, msg, args) {
      //return `This command is currently disabled`
      //if (!users.hasCmdAccess(msg)) return `You do not have permission to use this command`

      // alternate uses
      // toDo: mupen process command (users with access can cancel anything in the queue after providing an index)
      if (args.length == 1) {
        if (args[0].toUpperCase() == `CANCEL`) {
          for (var i = 0; i < MupenQueue.length; i++) {
            if (MupenQueue[i].user_id == msg.author.id && MupenQueue[i].process == null && !MupenQueue[i].skip) {
              MupenQueue[i].skip = true // mark to be skipped instead of removing it to try and avoid async problems
              var url = MupenQueue[i].m64_url.split('/')
              return `${url[url.length-1]} will be skipped` // gives filename
            }
          }
          return `You do not have an encode request in queue`

        } else if (args[0].toUpperCase() == `FORCESKIP` && (users.hasCmdAccess(msg) || msg.author.id == MupenQueue[0].user)) { // sending fake links can stall execution
          var encode = MupenQueue.shift()
          encode.process = 0 // ghost process is never killed. EncodingQueue[0].process.kill() // TODO: FIX THIS ?
          NextProcess(bot)
          return `Encode skipped: \`\`\`${JSON.stringify(encode)}\`\`\``

        } else if (args[0].toUpperCase() == `QUEUE`) {
		      var result = ``
          MupenQueue.forEach(async(process, index) => {
            result += `${index}. `
            if (process.user_id == null) {
              result += `[no user] `
            } else {
              var dm = await bot.getDMChannel(process.user_id) // no catch...
              result += `${dm.recipient.username} `
            }
            
            if (process.channel_id == null) {
              result += `(no channel)`
            } else if (process.channel_id == dm.id) {
              result += `(DM)`
            } else {
              result += `(<#${process.channel_id}>)`
            }

            result += '\n'
          })
          return result //`Queue length: ${EncodingQueue.length}` // TODO: maybe give more detailed info?
        }
      }


      // look for m64 & st as either a URL in the arguments, or an attachment
      var m64_url = ``
      var st_url = ``

      for (var i = 0; i < args.length; i++) {
        if (args[i].endsWith(`.m64`)) {
          m64_url = args[i]
        } else if (args[i].endsWith(`.st`) || args[i].endsWith(`.savestate`)) {
          st_url = args[i]
        }
      }

      for (var i = 0; i < msg.attachments.length; i++) {
        if (msg.attachments[i].url.endsWith(`.m64`)) {
          m64_url = msg.attachments[i].url
        } else if (msg.attachments[i].url.endsWith(`.st`) || msg.attachments[i].url.endsWith(`.savestate`)) {
          st_url = msg.attachments[i].url
        }
      }
	  
      if (!m64_url || !st_url) {
        return `Missing/Invalid Arguments: \`$encode [cancel/forceskip/queue/nolua] <m64> <st/savestate>\``
      }

      var filename = m64_url.split(`/`) // doesnt ensure it contains / because it should contain it...
      filename = filename[filename.length - 1]
      filename = filename.substring(0, filename.length - 4)
      
      var mupen_args = ["-m64", process.cwd()+save.getSavePath().substring(1)+"/tas.m64", "-avi", "encode.avi", "-lua", LUA_INPUTS]
      if (args.length && [`NOLUA`, `NO-LUA`, `DISABLE-LUA`].filter((a) => a == args[0].toUpperCase()).length) {
        mupen_args.splice(mupen_args.length-2, mupen_args.length) // remove last two args
      }

      var pos = QueueAdd(
        bot,
        m64_url,
        st_url,
        mupen_args,
        () => {
          var err = null
          if (fs.existsSync(`./encode.avi`)) {
            fs.unlinkSync(`./encode.avi`) // ERROR HANDLE BC THIS ACTUALLY THREW AND CRASHED
          }
          if (fs.existsSync(`./encode.mp4`)) fs.unlinkSync(`./encode.mp4`)
        },
        async () => {
          if (!fs.existsSync(`./encode.avi`)) {
            bot.createMessage(msg.channel.id, `Error: avi not found <@${msg.author.id}>`)
            return
          }

          var stats = fs.statSync(`./encode.avi`)
          if (stats.size == 0) {
            bot.createMessage(msg.channel.id, `Error: avi is 0 bytes. There was likely a crash when attempting to encode <@${msg.author.id}>`)
            return
          }
      
          bot.createMessage(msg.channel.id, `Uploading...`)
          try {
            cp.execSync(`ffmpeg -i encode.avi encode.mp4`) // TODO: detect if server is boosted (filesize limit) and pass -fs flag
            var filesize_limit = msg.channel.guild != undefined && msg.channel.guild.premiumTier >= 2 ? 50 : 8 // mb
            filesize_limit = filesize_limit * 1000000 // in bytes
            stats = fs.statSync(`./encode.mp4`)
            var reply = `Encode Complete <@${msg.author.id}>`
            if (stats.size > filesize_limit) { // trim video to fit
              reply += ` (filesize limit exceeded)`
              fs.renameSync(`./encode.mp4`, `./encode2.mp4`)
              cp.execSync(`ffmpeg -i encode2.mp4 -fs ${filesize_limit * 0.98} encode.mp4`) // leave room for header?
              fs.unlinkSync(`./encode2.mp4`)
            }
            var video = fs.readFileSync(`./encode.mp4`)
            await bot.createMessage(msg.channel.id, reply, {file: video, name: `${filename}.mp4`})
            fs.unlinkSync(`./encode.mp4`)
          } catch (err) {
            bot.createMessage(msg.channel.id, `Something went wrong <@${msg.author.id}> \`\`\`${err}\`\`\``)
          }
        },
        msg.channel.id,
        msg.author.id,
        2*60*30 + 30*30 // 2.5 min
      )
      
      if (pos == 1) {
        return "Queue position 1: your encode is processing..."
      } else if (EncodingQueue.length == 2) {
        return "Queue position 2: your encode will be processed next"
      }
      return `Queue position ${pos}`
    }
  },

  listcrc:{
    name: `ListCRC`,
    aliases: [],
    short_descrip: `See recognized games`,
    full_descrip: `Shows a list of ROM CRCs that the \`$encode\` command supports. If there is a game that you would like added to this list, please contact the owner of this bot`,
    hidden: true,
    function: async function(bot, msg, args) {
      var result = `CRC: ROM Name\n` + "```"
      crc = Object.keys(KNOWN_CRC)
      for (var i = 0; i < crc.length; i++) {
        result += `${crc[i]}: ${KNOWN_CRC[crc[i]]}\n`
      }
      return result + "```"
    }

  },
  
  load: function() {
    var data = save.readObject(`m64.json`)
	  MUPEN_PATH = data.MupenPath
	  GAME_PATH = data.GamePath
    LUA_INPUTS = data.InputLuaPath
    LUA_TIME_LIMIT = data.TimeoutLuaPath
	  Object.keys(data.CRC).forEach(crc => {
		  KNOWN_CRC[crc] = data.CRC[crc]
	  })
  },

  Process: QueueAdd
}
