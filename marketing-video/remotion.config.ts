import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Higher quality for the master render; bring down for fast previews.
Config.setCrf(18);
