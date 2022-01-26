/**
 * GeoJS Track Lines
 * Based on geo.trackFeature https://opengeoscience.github.io/geojs/apidocs/geo.trackFeature.html
 * Example implementation: https://opengeoscience.github.io/geojs/tutorials/tracks/
 *
 * Track layer is a-typical because it requires extra temporal context,
 * so it cannot be based on the a-temporal BaseLayer.
 */
import BaseLayer, { LayerStyle, BaseLayerParams, MarkerStyle } from 'vue-media-annotator/layers/BaseLayer';
import Track, { TrackId } from 'vue-media-annotator/track';
import { FrameDataTrack } from 'vue-media-annotator/layers/LayerTypes';
import { getTrack } from 'vue-media-annotator/use/useTrackStore';

interface TailData {
  trackId: TrackId;
  confidencePairs: [string, number] | null;
  selected: boolean;
  t: number; // GeoJS tail data t(time)
  x: number;
  y: number;
  interpolated: boolean;
}

export default class TailLayer extends BaseLayer<TailData[]> {
  currentFrame: number;

  before: number;

  after: number;

  markerSize: number;

  markerOpacity: number;

  /** Hold a reference to the trackMap */
  trackMap: Readonly<Map<number, Track>>;

  /** Cache data generation for the whole track */
  tailCache: Record<TrackId, TailData[]>;

  constructor(params: BaseLayerParams, trackMap: Readonly<Map<number, Track>>) {
    super(params);

    this.initialize();
    this.currentFrame = 0;
    this.before = 5;
    this.after = 10;
    this.markerSize = 8;
    this.markerOpacity = 1.0;
    this.trackMap = trackMap;
    this.tailCache = {};
  }

  generateDataForTrack(fd: FrameDataTrack): TailData[] {
    const track = getTrack(this.trackMap, fd.trackId);
    // const existing = this.tailCache[track.trackId];
    // if (existing) {
    //   return existing;
    // }
    this.tailCache[track.trackId] = track.features
      .slice(Math.max(this.currentFrame - this.before, 0), this.currentFrame + this.after)
      .filter((f) => !!f.bounds)
      .map((feature) => {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        const bounds = feature.bounds!!;
        return {
          trackId: track.trackId,
          confidencePairs: track.getType(),
          selected: fd.selected,
          t: feature.frame,
          x: bounds[0] + (bounds[2] - bounds[0]) / 2.0,
          y: bounds[1] + (bounds[3] - bounds[1]) / 2.0,
          interpolated: !!feature.interpolate,
        };
      });
    return this.tailCache[track.trackId];
  }

  initialize() {
    const layer = this.annotator.geoViewerRef.value.createLayer('feature', {
      features: ['line'],
    });
    this.featureLayer = layer.createFeature('track');
    super.initialize();
  }

  changeData(frameData: FrameDataTrack[]): void {
    const data = frameData.map((d) => this.generateDataForTrack(d));
    // console.log(data);
    this.featureLayer
      .data(data)
      .startTime(0)
      .endTime(this.currentFrame)
      .style(this.createStyles())
      .markerStyle(this.createMarkerStyle());
    this.featureLayer.pastStyle('strokeOpacity', 0);
    this.featureLayer.draw();
  }

  updateSettings(currentFrame: number) {
    this.currentFrame = currentFrame;
  }

  redraw() {
    throw new Error(`${this}.redraw Unimplemented`);
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  formatData(_: FrameDataTrack[]): TailData[][] {
    throw new Error(`${this}.formatData Unimplemented`);
  }

  disable() {
    this.featureLayer
      .data([])
      .draw();
  }

  createMarkerStyle(): MarkerStyle<TailData[]> {
    return {
      symbol: 16,
      symbolValue: [1, 1, 0, false],
      radius: this.markerSize,
      fillColor: (trackData: TailData[]) => {
        if (trackData[0]) {
          if (trackData[0].selected) {
            return this.stateStyling.selected.color;
          }
          if (trackData[0].confidencePairs) {
            return this.typeStyling.value.color(trackData[0].confidencePairs[0]);
          }
        }

        return this.typeStyling.value.color('');
      },
      strokeOpacity: this.markerOpacity,
      fillOpacity: 0.7,
      strokeColor: (trackData: TailData[]) => {
        if (trackData[0]) {
          if (trackData[0].selected) {
            return this.stateStyling.selected.color;
          }
          if (trackData[0].confidencePairs) {
            return this.typeStyling.value.color(trackData[0].confidencePairs[0]);
          }
        }

        return this.typeStyling.value.color('');
      },
    };
  }

  createStyles(): LayerStyle<TailData[]> {
    return {
      ...super.createStyle(),
      // Style conversion to get array objects to work in geoJS
      strokeColor: (point, _, trackData) => {
        if ((point as { interpolated: boolean }).interpolated) {
          return 'red';
        }
        if (trackData[0]) {
          if (trackData[0].selected) {
            return this.stateStyling.selected.color;
          }
          if (trackData[0].confidencePairs) {
            return this.typeStyling.value.color(trackData[0].confidencePairs[0]);
          }
        }
        return this.typeStyling.value.color('');
      },
      antialiasing: false,
      fill: false,
      strokeWidth: (_, __, data) => {
        if (data[0] && data[0].confidencePairs) {
          return this.typeStyling.value.strokeWidth(data[0].confidencePairs[0]) * 0.5;
        }

        return this.stateStyling.standard.strokeWidth * 0.5;
      },
      // strokeOpacity: this.markerOpacity,
    };
  }
}
