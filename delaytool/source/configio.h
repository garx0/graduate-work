#pragma once
#ifndef DELAYTOOL_CONFIGIO_H
#define DELAYTOOL_CONFIGIO_H

#include "tinyxml2/tinyxml2.h"
#include "algo.h"

constexpr int cellSizeDefault = 10; // bytes
constexpr int voqPeriodDefault = 100; // cells
constexpr double jitStartDefault = 0.5; // ms
constexpr int sminDefault = 64; // bytes

std::vector<int> TokenizeCsv(const std::string& str);

VlinkConfigOwn fromXml(tinyxml2::XMLDocument& doc, const std::string& scheme,
        int cellSize = cellSizeDefault, int voqPeriod = voqPeriodDefault);

// doc must already contain the resources and VL configuration
// (e.g. doc used for building config)
bool toXml(VlinkConfig* config, tinyxml2::XMLDocument& doc);

void DebugInfo(const VlinkConfig* config);

#endif //DELAYTOOL_CONFIGIO_H
