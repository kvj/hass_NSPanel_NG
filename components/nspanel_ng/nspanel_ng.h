#pragma once

#include "esphome/core/component.h"
#include "esphome/core/application.h"
#include "esphome/components/rtttl/rtttl.h"
#include "esphome/components/nextion/nextion.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/api/api_server.h"

#include "esphome/components/esp32_ble_server/ble_server.h"
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"
#include "esphome/components/esp32_ble_server/ble_2902.h"

#include <optional>

#define NS_PANEL_NG_VER "0.2.2"
// http://192.168.0.22/static/nspanel_ng_eu_0.2.tft

namespace esphome {
namespace nspanel_ng {

#define CT_PRESS 0
#define CT_RELEASE 1
#define CT_PENDING 2

#define CT_LONG_PRESS 800
#define CT_DOUBLE_DELAY 150

#define CT_NONE 0
#define CT_CLICK 1
#define CT_DOUBLE_CLICK 2
#define CT_LONG_CLICK 3

#define TFT_UPDATE_DELAY 15000

#define SCREENSAVER_CHANGE_MS 30000

#define BLE_SERVICE 0x2101
#define BLE_CHR_MAP 0x3101

struct ClickTracker {
    uint32_t action_ts;
    uint8_t  clicks;
    uint8_t  next_state;
};

struct CellContent {
    std::string type;
    uint16_t icon;
    std::string label;
    std::string value;
    std::string unit;
    int32_t color;
    int32_t bg_color;
};

struct TagGeometry {
    uint16_t x;
    uint16_t y;
    uint16_t w;
    uint16_t h;
};

class EasyBLEServer {
    protected:
        esphome::esp32_ble_server::BLEServer *ble_server = nullptr;
        bool ble_setup_complete = false;

        void ble_create_services();
        void ble_start_services();

    public:
        void set_ble_server(esphome::esp32_ble_server::BLEServer *ble_server) { this->ble_server = ble_server; }        

        void loop();
        
        bool ble_write_char(uint16_t svc_uuid, uint16_t chr_uuid, std::vector<uint8_t> data, bool notify);

};

class NSPanelNG : public esphome::Component, public esphome::nextion::NextionComponentBase, public EasyBLEServer {

    private:
        esphome::rtttl::Rtttl *rtttl_player;
        esphome::nextion::Nextion *display;
        esphome::switch_::Switch *relay1, *relay2;
        esphome::binary_sensor::BinarySensor *button1, *button2;
        esphome::api::APIServer *api_server;
        float brightness_ = 1.0;
        float off_brightness_ = 0.01;
        std::vector<ClickTracker> clicks;

        std::map<uint8_t, std::vector<uint8_t>> tag_to_cells = {};
        std::map<uint8_t, uint8_t> cell_to_tag = {};
        std::map<uint8_t, CellContent> tag_content = {};

        std::vector<int> pixels_ = {};
        uint8_t pixels_tag_ = 0;

        bool pixels_screensaver_ = false;
        uint16_t pixels_screensaver_dim_[3] = {0, 0, 0};
        uint32_t pixels_screensaver_change_ts_ = 0;

        int last_pixels_size = 0;

        std::string display_version_ = "Disconnected";
        std::string display_variant_;
        bool visual_feeback = true;
        std::string tft_url;
        long tft_update_start = -1;
        int center_icon_visibility = 0;
        uint32_t center_icon_blink_start = 0;

    public:

        void set_display(esphome::nextion::Nextion *display) { 
            this->display = display; 
        }
        void set_api_server(esphome::api::APIServer *api_server) { this->api_server = api_server; }
        void set_relays(esphome::switch_::Switch *relay1, esphome::switch_::Switch *relay2) {
            this->relay1 = relay1; 
            this->relay2 = relay2;
        }
        void set_buttons(esphome::binary_sensor::BinarySensor *button1, esphome::binary_sensor::BinarySensor *button2) {
            this->button1 = button1;
            this->button2 = button2;
        }
        void set_variant(const std::string variant) { this->display_variant_ = variant; }
        void set_rtttl_player(esphome::rtttl::Rtttl *rtttl_) { this->rtttl_player = rtttl_; }

        void setup() override;
        void loop() override;

        void process_text(const std::string &name, const std::string &value) override;

        void update_relay(const int index, const bool state);
        void update_backlight(const int value, const int off_value);
        void send_metadata();
        void upload_tft(const std::string path);
        void update_grid_cell(const int index, const std::string type_, const int icon, const std::string name, const std::string value, const std::string unit, const int color);
        void update_text(const int index, const std::string content, const int icon, const int color);
        void update_center_icon(const int icon, const int color, const int visibility);
        void play_sound(const std::string rtttl_content);

        void update_pixels(uint8_t tag, std::vector<int> pixels);
        void update_layout(std::vector<int> layout);
        void update_cell(uint8_t tag, CellContent content);

        void update_screensaver(const bool is_on, const int type);

    private:
        const std::string gen_icon_char(int icon);
        void send_hass_event(const std::string name, std::map<std::string, std::string> extra);
        void track_click(int index, bool press);
        uint8_t compute_click(int index);
        float _brightness_adjusted() { return brightness_ == 0? off_brightness_: brightness_; }

        TagGeometry calc_geometry(uint8_t tag);
        void render_cell(uint8_t tag, bool with_bg, esphome::Color bg_color);

        void process_touch(uint16_t x, uint16_t y, bool on);

        void nextion_xstr(uint16_t x, uint16_t y, uint16_t w, u_int16_t h, uint8_t font, esphome::Color color, esphome::Color bg_color, uint8_t ha, std::string text);

        void draw_pixels(uint16_t x, uint16_t y, uint16_t w, bool clear);

};

}
}
