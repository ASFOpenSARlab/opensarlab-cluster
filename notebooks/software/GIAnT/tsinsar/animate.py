'''Matplotlib's animation module rewritten for GIAnT with minor changes.'''
import matplotlib.animation as mA
from matplotlib import verbose
from matplotlib.cbook import iterable
import itertools

class Animation(mA.Animation):
    '''Matplotlib.animation modified to include high resolution and transparency effects. Currently only the FFmpeg part has been modified.'''

    def ffmpeg_cmd(self, fname, fps, codec, frame_prefix):
        '''ffmpeg command modified to include sameq for higher resolution movies.'''
        return ['ffmpeg', '-y', '-r', str(fps),'-b', '1800k', '-sameq', '-i', '%s%%04d.png' % frame_prefix, fname]

    def save(self, filename, fps=5, codec='mpeg4', clear_temp=True, frame_prefix='_tmp', transp=False, dpi=None):

        if self._first_draw_id is not None:
            self._fig.canvas.mpl_disconnect(self._first_draw_id)
            reconnect_first_draw = True
        else:
            reconnect_first_draw = False

        fnames = []
        for idx,data in enumerate(self.new_saved_frame_seq()):
            #TODO: Need to see if turning off blit is really necessary
            self._draw_next_frame(data, blit=False)
            fname = '%s%04d.png' % (frame_prefix, idx)
            fnames.append(fname)
            verbose.report('Animation.save: saved frame %d to fname=%s'%(idx, fname), level='debug')
            self._fig.savefig(fname, transparent=transp, dpi=dpi)

        self._make_movie(filename, fps, codec, frame_prefix)

        if clear_temp:
            import os
            verbose.report('Animation.save: clearing temporary fnames=%s'%str(fnames), level='debug')
            for fname in fnames:
                os.remove(fname)

        # Reconnect signal for first draw if necessary
        if reconnect_first_draw:
            self._first_draw_id = self._fig.canvas.mpl_connect('draw_event',
                self._start)


class TimedAnimation(Animation):
    '''Timed Animation using our new Animation module. Copied from matplotlib.animation.'''
    def __init__(self, fig, interval=200, repeat_delay=None, repeat=True, event_source=None, *args, **kwargs):
        '''Redefining init as it includes call to base class.'''
        self._interval = interval
        self._repeat_delay = repeat_delay
        self.repeat = repeat

        if event_source is None:
            event_source = fig.canvas.new_timer()
            event_source.interval = self._interval

        Animation.__init__(self, fig, event_source=event_source, *args, **kwargs)

    def _step(self, *args):
        '''Redefining as it includes call to base class.'''
        still_going = Animation._step(self, *args)
        if not still_going and self.repeat:
            if self._repeat_delay:
                self.event_source.remove_callback(self._step)
                self.event_source.add_callback(self._loop_delay)
                self.event_source.interval = self._repeat_delay
            self.frame_seq = self.new_frame_seq()
            return True
        else:
            return still_going


    def _stop(self, *args):
        self.event_source.remove_callback(self._loop_delay)
        Animation._stop(self)

    def _loop_delay(self, *args):
        self.event_source.remove_callback(self._loop_delay)
        self.event_source.interval = self._interval
        self.event_source.add_callback(self._step)

class FuncAnimation(TimedAnimation):
    ''' Redefined FuncAnimation as includes calls to baseclass. Copied from matplotlib.animation.'''
    def __init__(self, fig, func, frames=None ,init_func=None, fargs=None,
            save_count=None, **kwargs):
        if fargs:
            self._args = fargs
        else:
            self._args = ()
        self._func = func
        self.save_count = save_count

        if frames is None:
            self._iter_gen = itertools.count
        elif callable(frames):
            self._iter_gen = frames
        elif iterable(frames):
            self._iter_gen = lambda: iter(frames)
            self.save_count = len(frames)
        else:
            self._iter_gen = lambda: iter(range(frames))
            self.save_count = frames

        if self.save_count is None:
            self.save_count = 100

        self._init_func = init_func

        self._save_seq = []

        TimedAnimation.__init__(self, fig, **kwargs)

        self._save_seq = []

    def new_frame_seq(self):
        return self._iter_gen()

    def new_saved_frame_seq(self):
        if self._save_seq:
            return iter(self._save_seq)
        else:
            return itertools.islice(self.new_frame_seq(), self.save_count)

    def _init_draw(self):
        if self._init_func is None:
            self._draw_frame(self.new_frame_seq().next())
        else:
            self._drawn_artists = self._init_func()

    def _draw_frame(self, framedata):
        self._save_seq.append(framedata)

        self._save_seq = self._save_seq[-self.save_count:]

        self._drawn_artists = self._func(framedata, *self._args)
