process.title = "CompBOT";
console.log("Starting main.js...");

// other js files
var fs = require("fs");
const Eris = require("eris");

const miscfuncs = require("./miscfuncs.js");
const users = require("./users.js");
const comp = require("./comp.js");
const score = require("./score.js");
const save = require("./save.js");

// make new cfg file if it doesn't exist
if (!fs.existsSync("save.cfg"))
	save.makeNewSaveFile();

// channels of interest
var CHANNELS = {"GENERAL": "397488794531528704",
		"BOT": "554820730043367445",
		"BOT_DMS": "555543392671760390",
		"SCORE": "529816535204888596",
		"RESULTS": "529816480016236554",
		"CURRENT_SUBMISSIONS": "397096356985962508",
		"OTHER": "267091686423789568",
		"MARIO_GENERAL": "267091914027696129",
		"TASBOTTESTS": "562818543494889491"}

const GUILDS = {"COMP":"397082495423741953","ABC":"267091686423789568"}

const COMP_ACCOUNT = "397096658476728331";
const SCORE_POINTER = "569918196971208734";
const BOT_ACCOUNT = "555489679475081227"; // better way to identify self?
const XANDER = "129045481387982848";

// token
const CompBot = "NTU1NDg5Njc5NDc1MDgxMjI3.D2smAQ.wJYGkGHK5mdC15kEX3_0wThBA7w";
var bot = new Eris.CommandClient(CompBot, {}, {
	description: "List of commands",
	owner: "Eddio0141, Barry & Xander",
	prefix: "$"
});

bot.on("ready", () => {
	score.retrieveScore(bot);
	bot.getSelf().then((self) => {
		console.log(self.username + " Ready! (" + miscfuncs.getDateTime() + ")");
	})
});

function addCommand(name, func, descrip, fullDescrip, hide){
	bot.registerCommand(name, (msg, args) => {
		return func(bot, msg, args); // pass arguments to the function
	},
	{
		description: descrip,
		fullDescription: fullDescrip,
		hidden: hide,
		caseInsensitive: true
	});
}

function ping(bot, msg, args){
	if (args.length < 1)
		return "baited (" + (new Date().getTime() - msg.timestamp) / 1000 + "ms)";
}

// public commands
addCommand("ping", ping, "ping", "To check if the bot is not dead. Tells you time it takes to bait you in ms", false);

// specials
// this command doesnt do anything...
bot.registerCommand("restart", (msg, args) => {
	if (users.hasCmdAccess(msg.member)) {
		restart();
	}
},
{
	description: "restarts bot",
	fullDescription: "This restarts bot.",
	hidden: true
});

bot.registerCommand("test", (msg, args) => {
	if (users.hasCmdAccess(msg.member)){
		console.log("test command called");
		//miscfuncs.makeFolderIfHNotExist("./taskuploads/");
		//miscfuncs.downloadFromUrl(msg.attachments[0].url, "./taskuploads/" + msg.attachments[0].filename);
		//return "done saving " + msg.attachments[0].filename;

		//save.makeNewSaveFile();
	}
},
{
	description: "test (don't use)",
	fullDescription: "its a test command (don't use)",
	hidden: true
});


function uptime(bot, msg, args){
	bot.createMessage(msg.channel.id, miscfuncs.formatSecsToStr(process.uptime()));
	console.log("uptime : " + miscfuncs.formatSecsToStr(process.uptime()));
}
addCommand("uptime", uptime, "Prints uptime", "Prints how long the bot has been connected", false);



bot.registerCommand("starttask", (msg, args) => {
	if (users.hasCmdAccess(msg.member) && args.length == 1) {
		var tasknum = Number(args[0]);
		if (Number.isNaN(tasknum))
			return "Invalid argument, needs task number instead";

		// empty out folder
		miscfuncs.deleteFilesInFolder("./taskuploads/");
		miscfuncs.makeFolderIfNotExist("./taskuploads/");

		comp.allowSubmission(tasknum);

		//save.saveAllowsubmissionAndTaskNum(comp.getAllowSubmission, getTaskNum);

		return "starting task " + args[0];
	}
	return "Enter task number after the $starttask";
},
{
	description: "Now accepts file uploads in dms for tas comp entry",
	fullDescription: "Arguments : task number",
	hidden: true
});


//addCommand("score", score.processCommand, "Edits #score", "Usage: ``$score <action> <parameters>``\nAnyone may use ``$score calculate`` and ``$score find <me or name>``", false)
bot.registerCommand("score", (msg, args) => {return score.processCommand(bot, msg, args);},
{description: "Edits #score", fullDescription: "Usage: ``$score <action> <parameters>``"});



// message handle
bot.on("messageCreate", (msg) => {

	// auto add planes to smileys
	if (msg.content.indexOf("😃") != -1){
		bot.addMessageReaction(msg.channel.id, msg.id, "✈");
	}

	if (msg.author.id == BOT_ACCOUNT){return;} // ignore messages from self

	// handle task submissions
	if (msg.attachments.length > 0 && !users.isBanned(msg.author) && miscfuncs.isDM(msg) && comp.getAllowSubmission()) {
		bot.createMessage(msg.channel.id, "ye");
	}

	// message in #results (non-DQ) => calculate score
	if (msg.channel.id == CHANNELS.RESULTS && msg.content.split("\n")[0].toUpperCase().indexOf("DQ") == -1){

		var message = score.updateScore(msg.content);

		bot.createMessage(CHANNELS.SCORE, message).then((msg)=>{
			// store the message so it may be edited
    	score.setScoreMsg(msg.channel.id, msg.id);
			bot.getDMChannel(COMP_ACCOUNT).then((channel) => {
				channel.editMessage(SCORE_POINTER, msg.channel.id + " " + msg.id);
			});
		});
	}


 	// Redirect Direct Messages that are sent to the bot
	// doesn't expose people who have command access
	if (miscfuncs.isDM(msg) && !miscfuncs.hasCmdAccess(msg)){

		var message = "["+msg.author.username + "]: " + msg.content;

		// Redirect to a specific channel
		//bot.createMessage(CHANNELS.BOT_DMS, message);

		// Redirect to a specific user (feel free to change when testing for yourself)
		bot.getDMChannel(XANDER).then((dm) => {dm.createMessage(message);});

	}

});


// Channel Commands (Allowed from #bot and #tasbottests)
const alt = require("./altcommands.js");
addCommand("ls", alt.getChannelAliases, "Retrieves the list of recognized channels", "Retrieves the list of channel aliases with their ids", false);
addCommand("addChannel", alt.addChannelAlias, "Adds a shortcut for a ID", "Usage: ``$addChannel <alias> <channel_id>``\nAllows ``<alais>`` to be specified in place of ``<channel_id>`` for other commands.", false);
addCommand("removeChannel", alt.removeChannelAlias, "Removes a channel alias from the database", "Usage: ``$removeChannel <alias>``", false);

// Chat Commands (Allowed from #bot and #tasbottests)
addCommand("send", alt.send, "Sends a message to a specified channel", "Usage: ``$send <channel_id or alias> <message>``\nFor a list of aliases use ``$ls``", true);
addCommand("delete", alt.delete, "Deletes a message", "Usage: ``$delete <channel_id or alias> <message_id>``\nFor a list of aliases use ``$ls``", true);
addCommand("pin", alt.pin, "Pins a message", "Usage: ``$pin <channel_id or alias> <message_id>``\nFor a list of aliases use ``$ls``", true);
addCommand("unpin", alt.unpin, "Unpins a message", "Usage: ``$unpin <channel_id or alias> <message_id>``\nFor a list of aliases use ``$ls``", true);
addCommand("dm", alt.dm, "Sends a message to a user", "Usage: ``$dm <user_id> <message...>``\nThe message may contain spaces", true);


/*
		case "$addCmdAccess":
			if (users.hasCmdAccess(msg.member) && msg.content.split(" ").length == 2) {
				var user = msg.content.split(" ", 2)[1].replace("@", "");
				users.addCmdAccess(user);
				bot.createMessage(msg.channel.id, "successfully added user " + user + " to CmdAccess");
				console.log("successfully added user " + user + " to CmdAccess");
			}
			break;
		case "$addBan":
			if (users.hasCmdAccess(msg.member) && msg.content.split(" ").length == 2) {
				var user = msg.content.split(" ", 2)[1].replace("@", "");
				users.addBan(user);
				bot.createMessage(msg.channel.id, "successfully banned user " + user);
				console.log("successfully banned user " + user);
			}
			break;
*/

// add any reaction added to any message
var echoReactions = false;
bot.on("messageReactionAdd", (msg, emoji) => {

	if (!echoReactions){return;}

	reaction = emoji.name;
	if (emoji.id != null){
		reaction += ":" + emoji.id;
	}
	bot.addMessageReaction(msg.channel.id, msg.id, reaction)

	if (emoji.name == "😃"){ // auto add planes to smileys
		bot.addMessageReaction(msg.channel.id, msg.id, "✈");
	}

});

bot.registerCommand("toggleReaction", (msg, args) => {
	if (!miscfuncs.hasCmdAccess(msg)) {return;}

	echoReactions = !echoReactions;
	return echoReactions ? "Reactions enabled" : "Reactions disabled";

},
{
	description: "Toggle auto reactions (tr)",
	fullDescription: "Switches echoing reactions on/off",
	hidden: false
});

bot.registerCommand("react", (msg, args) => {
	if (args[2].includes(":")){
		args[2] = args[2].substr(2, args[2].length-3);
	}
	bot.addMessageReaction(chooseChannel(args[0]), args[1], args[2]).catch((err) => {return;});
},
{
	description: "React to a message (This is broken ?)",
	hidden: true
});


const Submitted = "575732673402896404";
const RevealStreamer = "405161681769988096";
bot.registerCommand("add", (msg, args) => {
	if (miscfuncs.hasCmdAccess(msg)){
		var member = msg.member.id;
		if (args[1] != undefined){
			member = args[1];
		}
		msg.channel.guild.addMemberRole(member, args[0], "He asked nicely")
		return "Gave user " + member + " Role " + args[0];
		/* cycle through all the roles and print them
		var roles = msg.channel.guild.roles;
		roles.forEach((role) => {
			bot.createMessage(msg.channel.id, role.name + " " + role.id)
		})
		return "List Complete"*/
	}
},
{
	description: "This message should not appear",
	fullDescription: "This message should not appear",
	hidden: true
});

bot.registerCommand("rm", (msg, args) => {
	if (miscfuncs.hasCmdAccess(msg)){
		var member = msg.member.id;
		if (args[1] != undefined){
			member = args[1];
		}
		msg.channel.guild.removeMemberRole(member, args[0], "He asked for it")
		return "Removed Role "+args[0]+" from user " + member;
	}
},
{
	description: "This message should not appear",
	fullDescription: "This message should not appear",
	hidden: true
});

bot.registerCommand("log", (msg, args) => {
	if (!miscfuncs.hasCmdAccess(msg)){return;}
	console.log(msg.content);
},
{
	description: "Logs the message in the console",
	hidden: true
});

// Games
const game = require("./game.js");
addCommand("toggleGames", game.toggle, "Toggle game functions (tg)", "Switches the game functions on/off", false);
addCommand("giveaway", game.giveaway, "Randomly selects from a list", "Randomly selects a winner from line separated entries for a giveaway", false)
addCommand("slots", game.slots, "Spin to win", "Chooses a number of random emojis. This number is specified by the user and defaults to 3. The limit is as many characters as can fit in one message",true);

// Announcements
addCommand("ac", alt.announce, "Announces a message", "Usage: ``$ac <channel> <hour> <minute> [message]``\nHours must be in 24 hour.\nUses current date.\nHas a default message", false);
addCommand("acclear", alt.clearAnnounce, "Removes all planned announcements", "Removes all planned announcements", true);


// Various Command Aliases (<Alias>, <Original_Command_Name>)
aliases = [
	["channeladd", "addChannel"],
	["channelremove", "removeChannel"],
	["listchannels", "ls"],
	["getchannels", "ls"],
	["say", "send"],
	["tr", "toggleReaction"],
	["togglereactions", "toggleReaction"],
	["tg", "toggleGames"],
	["togglegame", "toggleGames"]
];

aliases.forEach((alias)=>(bot.registerCommandAlias(alias[0], alias[1])));

bot.registerCommand("a", (msg, args) => {
	//if (!miscfuncs.hasCmdAccess(msg)) {return;}
	bot.createMessage(msg.channel.id, {content: "@everyone", disableEveryone: false})
	//return "<&"+msg.channel.guild.id+">"

},
{
	description: "",
	fullDescription: "Usage: ``$``",
	hidden: true,
	caseInsensitive: true
});


bot.connect();

/* Command Template
bot.registerCommand("", (msg, args) => {
	if (!miscfuncs.hasCmdAccess(msg)) {return;}

	// Code here:

},
{
	description: "",
	fullDescription: "Usage: ``$``",
	hidden: true,
	caseInsensitive: true
});
*/
